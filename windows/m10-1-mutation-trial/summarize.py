"""Summarize the probe's existing evidence; does not run or mutate Source."""
import csv
import json
from pathlib import Path
from probe import TARGET_CALLS

HERE = Path(__file__).resolve().parent


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    results = json.loads((HERE / "results.json").read_text())
    for result in results:
        target = TARGET_CALLS.get(result["id"])
        calls = json.loads((HERE / result["id"] / "api-calls.json").read_text())
        reached = bool(calls.get(target, 0)) if target else None
        result.update(api_target_function=target, api_function_calls=calls.get(target, 0), api_target_reached=reached,
                      api_coverage=("reached" if reached else "not reached by LocalBackend") + "; confirmed by api-calls.json")
        save(HERE / result["id"] / "result.json", result)
    save(HERE / "results.json", results)
    valid = [r for r in results[1:] if r["valid"]]
    reachable = [r for r in valid if r["api_target_reached"]]
    baseline = json.loads((HERE / "baseline/api.json").read_text())
    summary = {
        "baseline": {"scenarios": 22, "steps": len(baseline),
                     "passing_steps": sum(not r["failures"] for r in baseline),
                     "failed_steps": sum(bool(r["failures"]) for r in baseline),
                     "failed_scenarios": len({r["scenario"] for r in baseline if r["failures"]}),
                     "shape_layer_only_bad_steps": sum(bool(r["shape"]) for r in baseline),
                     "unit": results[0]["unit"]},
        "valid_mutants": len(valid), "invalid_mutants": len(results) - 1 - len(valid),
        "api": {"all": len(valid), "reachable": len(reachable),
                "killed": sum(r["api_killed"] for r in valid),
                "reachable_survived": sum(not r["api_killed"] for r in reachable),
                "unreachable": sum(not r["api_target_reached"] for r in valid)},
        "unit": {"killed": sum(r["unit_killed"] for r in valid),
                 "survived": sum(not r["unit_killed"] for r in valid)},
        "joint": {"killed": sum(r["api_killed"] or r["unit_killed"] for r in valid),
                  "survived": sum(not (r["api_killed"] or r["unit_killed"]) for r in valid)},
    }
    summary["joint"]["survived_percent"] = round(100 * summary["joint"]["survived"] / len(valid), 2)
    save(HERE / "summary.json", summary)
    with (HERE / "mutants.tsv").open("w") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["mutant", "target", "fault", "api", "unit", "joint", "new_api_facets", "unit_failures"])
        for r in valid:
            api = "unreachable" if not r["api_target_reached"] else "killed" if r["api_killed"] else "survived"
            writer.writerow([r["id"], r["target"], r["description"], api,
                             "killed" if r["unit_killed"] else "survived",
                             "killed" if r["api_killed"] or r["unit_killed"] else "survived",
                             json.dumps(r["api_new_facets"]), json.dumps(r["unit"]["failures"])])
    with (HERE / "baseline-failures.tsv").open("w") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["scenario", "step", "shared_tsv_line", "operation", "actual_status", "facets"])
        for r in baseline:
            if r["failures"]:
                writer.writerow([r["scenario"], r["step"], r["line"], r["operation"], r.get("status"),
                                 json.dumps(r["failures"], ensure_ascii=False)])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
