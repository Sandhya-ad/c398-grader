from django.shortcuts import render
from rest_framework import status
from pathlib import Path
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse
from io import BytesIO
import zipfile
import time
import json
import statistics
import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt


from .omr import mark_file, mark_single_file


class DemoGradeView(APIView):

    def post(self, request):
        exam = request.FILES.get('exam')
        answer = request.FILES.get('answer_key')
        if not exam or not answer:
            return Response({'error': 'Provide both exam and answer_key'}, status=400)

        # mock result for MVP
        result = {"score": 8, "total": 10, "details": [
            {"q": 1, "correct": True},
            {"q": 2, "correct": False},
            {"q": 3, "correct": True},
        ]}
        return Response({"message": "Exam graded successfully (demo)", "result": result})


class GradeSingleView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):

        attempt_pdf = request.FILES.get("attempt_pdf")
        answer_key = request.FILES.get("answer_key")
        if not attempt_pdf or not answer_key:
            return Response({"detail": "attempt_pdf and answer_key are required"}, status=400)

        if attempt_pdf.content_type != "application/pdf" or answer_key.content_type != "application/pdf":
            return Response({"detail": "Both files must be PDFs"}, status=400)

        # Read once!
        attempt_bytes = attempt_pdf.read()
        answer_bytes = answer_key.read()

        try:
            marked_bytes = mark_single_file(attempt_bytes, answer_bytes)  # -> bytes
        except AssertionError as e:
            return Response({"detail": str(e)}, status=400)
        except Exception as e:
            return Response({"detail": f"Marking failed: {e}"}, status=500)

        resp = HttpResponse(marked_bytes, content_type="application/pdf")
        filename = f'Graded_{attempt_pdf.name or "exam"}.pdf'
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp


class GradeBatchView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        answer_key = request.FILES.get("answer_key")
        attempts = request.FILES.getlist("attempts")
        if not answer_key or not attempts:
            return Response({"detail": "answer_key and attempts[] required"}, status=400)

        if answer_key.content_type != "application/pdf":
            return Response({"detail": "answer_key must be PDF"}, status=400)
        for f in attempts:
            if f.content_type != "application/pdf":
                return Response({"detail": f"{f.name} is not a PDF"}, status=400)

        # Read answer
        answer_bytes = answer_key.read()

        # results: list of (filename, score, total, marked_bytes)
        results = []
        for f in attempts:
            attempt_bytes = f.read()
            try:
                score, total, marked = mark_file(attempt_bytes, answer_bytes)  # -> (score, total, bytes)
                results.append((f.name, score, total, marked))
            except AssertionError as e:
                return Response({"detail": f"{f.name}: {e}"}, status=400)
            except Exception as e:
                return Response({"detail": f"{f.name}: {e}"}, status=500)

        # ---- build per-attempt JSON + stats ----
        attempts_json = []
        scores = []
        percents = []

        for name, score, total, marked in results:
            pct = (100.0 * score / total) if total else 0.0
            scores.append(score)
            percents.append(pct)
            attempts_json.append({
                "filename": name,
                "score": score,
                "total": total,
                "percent": round(pct, 2),
            })

        # simple stats
        stats = {}
        if scores:
            stats = {
                "num_attempts": len(scores),
                "score_min": min(scores),
                "score_max": max(scores),
                "score_mean": round(statistics.mean(scores), 2),
                "percent_min": round(min(percents), 2),
                "percent_max": round(max(percents), 2),
                "percent_mean": round(statistics.mean(percents), 2),
            }
            if len(scores) >= 2:
                stats["score_median"] = round(statistics.median(scores), 2)
                stats["percent_median"] = round(statistics.median(percents), 2)

        stats_payload = {
            "attempts": attempts_json,
            "stats": stats,
        }

        # ---- generate a score distribution plot as PNG ----
        graph_bytes = None
        if percents:
            fig, ax = plt.subplots()
            ax.hist(percents, bins=10)
            ax.set_xlabel("Score (%)")
            ax.set_ylabel("Number of students")
            ax.set_title("Score Distribution")

            img_buf = BytesIO()
            fig.savefig(img_buf, format="png", bbox_inches="tight")
            plt.close(fig)
            img_buf.seek(0)
            graph_bytes = img_buf.getvalue()

        # ---- Build ZIP with PDFs, summary.csv, stats.json, and graph.png ----
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # CSV summary
            lines = ["filename,score,total,percent"]
            for row in attempts_json:
                lines.append(
                    f'{row["filename"]},{row["score"]},{row["total"]},{row["percent"]:.2f}'
                )
            zf.writestr("summary.csv", "\n".join(lines))

            # JSON stats
            zf.writestr("stats.json", json.dumps(stats_payload, indent=2))

            # PNG graph (optional – only if we had data)
            if graph_bytes is not None:
                zf.writestr("score_distribution.png", graph_bytes)

            # graded PDFs
            for name, score, total, marked in results:
                zf.writestr(f"Graded_{name}", marked)

        buf.seek(0)
        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="graded_{int(time.time())}.zip"'
        return resp
