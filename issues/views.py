import json
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import CriticalIssue, Issue, LowPriorityIssue, Reporter


DATA_DIR = Path(__file__).resolve().parent.parent
REPORTERS_FILE = DATA_DIR / "reporters.json"
ISSUES_FILE = DATA_DIR / "issues.json"


def _read_records(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as data_file:
        return json.load(data_file)


def _write_records(path, records):
    with path.open("w", encoding="utf-8") as data_file:
        json.dump(records, data_file, indent=2)


def _request_data(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Invalid JSON")


def _next_id(records):
    return max((record["id"] for record in records), default=0) + 1


@csrf_exempt
def reporters(request):
    if request.method == "POST":
        try:
            data = _request_data(request)
            reporter = Reporter(
                _next_id(_read_records(REPORTERS_FILE)),
                data.get("name"),
                data.get("email", ""),
                data.get("team", ""),
            )
            reporter.validate()
        except (ValueError, TypeError, KeyError) as error:
            return JsonResponse({"error": str(error)}, status=400)

        records = _read_records(REPORTERS_FILE)
        reporter_data = reporter.to_dict()
        records.append(reporter_data)
        _write_records(REPORTERS_FILE, records)
        return JsonResponse(reporter_data, status=201)

    if request.method == "GET":
        records = _read_records(REPORTERS_FILE)
        record_id = request.GET.get("id")
        if record_id is not None:
            try:
                record_id = int(record_id)
            except ValueError:
                return JsonResponse({"error": "Invalid reporter ID"}, status=400)
            for reporter in records:
                if reporter["id"] == record_id:
                    return JsonResponse(reporter, status=200)
            return JsonResponse({"error": "Reporter not found"}, status=404)
        return JsonResponse(records, safe=False, status=200)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def issues(request):
    if request.method == "POST":
        try:
            data = _request_data(request)
            reporter_id = data.get("reporter_id")
            if not isinstance(reporter_id, int):
                raise ValueError("Reporter ID must be an integer")
            if not any(
                reporter["id"] == reporter_id
                for reporter in _read_records(REPORTERS_FILE)
            ):
                raise ValueError("Reporter not found")

            issue = {
                "low": LowPriorityIssue,
                "critical": CriticalIssue,
            }.get(data.get("priority"), Issue)(
                _next_id(_read_records(ISSUES_FILE)),
                data.get("title"),
                data.get("description", ""),
                data.get("status"),
                data.get("priority"),
                reporter_id,
            )
            issue.validate()
        except (ValueError, TypeError, KeyError) as error:
            return JsonResponse({"error": str(error)}, status=400)

        records = _read_records(ISSUES_FILE)
        issue_data = issue.to_dict()
        issue_data["message"] = issue.describe()
        stored_issue = {key: value for key, value in issue_data.items() if key != "message"}
        records.append(stored_issue)
        _write_records(ISSUES_FILE, records)
        return JsonResponse(issue_data, status=201)

    if request.method == "GET":
        records = _read_records(ISSUES_FILE)
        record_id = request.GET.get("id")
        status = request.GET.get("status")
        if record_id is not None:
            try:
                record_id = int(record_id)
            except ValueError:
                return JsonResponse({"error": "Invalid issue ID"}, status=400)
            for issue in records:
                if issue["id"] == record_id:
                    return JsonResponse(issue, status=200)
            return JsonResponse({"error": "Issue not found"}, status=404)
        if status is not None:
            records = [issue for issue in records if issue["status"] == status]
        return JsonResponse(records, safe=False, status=200)

    return JsonResponse({"error": "Method not allowed"}, status=405)
