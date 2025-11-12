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

from .omr import mark_file, mark_single_file

API_KEY = None  # set to a string or env if you want to require it
def require_api_key(request):
    global API_KEY
    if not API_KEY:
        return  # no auth required if unset
    if request.headers.get("X-API-Key") != API_KEY:
        return Response({"detail": "Unauthorized"}, status=401)


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
        # (optional) api key check
        auth_fail = require_api_key(request)
        if auth_fail:
            return auth_fail

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
        # (optional) api key check
        auth_fail = require_api_key(request)
        if auth_fail:
            return auth_fail

        answer_key = request.FILES.get("answer_key")
        attempts = request.FILES.getlist("attempts")
        if not answer_key or not attempts:
            return Response({"detail": "answer_key and attempts[] required"}, status=400)

        if answer_key.content_type != "application/pdf":
            return Response({"detail": "answer_key must be PDF"}, status=400)
        for f in attempts:
            if f.content_type != "application/pdf":
                return Response({"detail": f"{f.name} is not a PDF"}, status=400)

        # Read answer once!
        answer_bytes = answer_key.read()

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

        # Build ZIP
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # add each graded file and a summary.csv
            lines = ["filename,score,total,percent"]
            for name, score, total, marked in results:
                pct = (100.0 * score / total) if total else 0.0
                lines.append(f'{name},{score},{total},{pct:.2f}')
                zf.writestr(f"Graded_{name}", marked)
            zf.writestr("summary.csv", "\n".join(lines))
        buf.seek(0)

        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="graded_{int(time.time())}.zip"'
        return resp
