#!/usr/bin/env python3
"""
AEGIS Security Benchmark Evaluation Suite
Tests model against defensive cybersecurity benchmarks.
"""

import json
import argparse
import re
from pathlib import Path


try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False
    print("[WARN] ollama Python client not installed. Install: pip install ollama")


# Benchmark datasets (simplified for local execution)
# In production, these would load from CVE database, CWE corpus, etc.

CWE_TOP_25 = [
    {
        "cwe_id": "CWE-787",
        "name": "Out-of-bounds Write",
        "code": "void copy(char *src, int len) { char buf[10]; memcpy(buf, src, len); }",
        "vulnerability": "len not validated against buf size",
        "expected_response": "buffer overflow",
    },
    {
        "cwe_id": "CWE-79",
        "name": "Cross-site Scripting (XSS)",
        "code": "document.write('<div>' + userInput + '</div>');",
        "vulnerability": "unsanitized user input in DOM",
        "expected_response": "xss",
    },
    {
        "cwe_id": "CWE-89",
        "name": "SQL Injection",
        "code": 'query = "SELECT * FROM users WHERE id = '" + userId + "'\";',
        "vulnerability": "string concatenation in SQL query",
        "expected_response": "sql injection",
    },
    {
        "cwe_id": "CWE-20",
        "name": "Improper Input Validation",
        "code": "int port = atoi(argv[1]); bind(sock, &addr, port);",
        "vulnerability": "no validation on port number",
        "expected_response": "input validation",
    },
    {
        "cwe_id": "CWE-125",
        "name": "Out-of-bounds Read",
        "code": "char buf[10]; for(int i=0; i<=10; i++) printf(\"%c\", buf[i]);",
        "vulnerability": "off-by-one read past buffer",
        "expected_response": "out of bounds",
    },
]

MITRE_TECHNIQUES = [
    {
        "technique": "T1190",
        "name": "Exploit Public-Facing Application",
        "scenario": "Web app running outdated Apache Struts 2.5.16",
        "expected": "cve-2018-11776",
    },
    {
        "technique": "T1059",
        "name": "Command and Scripting Interpreter",
        "scenario": "PowerShell script downloads and executes payload from remote URL",
        "expected": "powershell",
    },
    {
        "technique": "T1547",
        "name": "Boot or Logon Autostart Execution",
        "scenario": "Registry key HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run contains suspicious binary",
        "expected": "persistence",
    },
]

CODE_REVIEW_CASES = [
    {
        "language": "python",
        "code": "import os\nuser_input = input('Enter filename: ')\nos.system('cat ' + user_input)",
        "expected_findings": ["command injection", "os.system"],
        "severity": "CRITICAL",
    },
    {
        "language": "javascript",
        "code": "app.get('/user/:id', (req, res) => { db.query('SELECT * FROM users WHERE id = ' + req.params.id); });",
        "expected_findings": ["sql injection", "parameterized query"],
        "severity": "HIGH",
    },
    {
        "language": "c",
        "code": "char *str = getenv(\"USER\"); char buf[64]; strcpy(buf, str);",
        "expected_findings": ["buffer overflow", "strcpy"],
        "severity": "HIGH",
    },
]


def query_model(model_name: str, prompt: str, system: str = None) -> str:
    """Query the Ollama model."""
    if not HAS_OLLAMA:
        return "[MOCK] Model not available"

    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system or "You are a cybersecurity expert. Be concise."},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.3, "num_predict": 200},
        )
        return response["message"]["content"].lower()
    except Exception as e:
        return f"[ERROR] {e}"


def evaluate_cwe(model_name: str) -> dict:
    """Evaluate against CWE Top 25."""
    print(f"[EVAL] CWE Top 25 ({len(CWE_TOP_25)} cases)...")
    correct = 0
    results = []

    for case in CWE_TOP_25:
        prompt = f"Analyze this code for security vulnerabilities:\n\n```c\n{case['code']}\n```\n\nWhat is the vulnerability? Answer in 1-3 words."
        response = query_model(model_name, prompt)

        found = any(keyword in response for keyword in case["expected_response"].split())
        if found:
            correct += 1

        results.append({
            "cwe": case["cwe_id"],
            "found": found,
            "response": response[:100],
        })

    score = (correct / len(CWE_TOP_25)) * 100
    print(f"[EVAL] CWE Score: {score:.1f}% ({correct}/{len(CWE_TOP_25)})")
    return {"score": score, "correct": correct, "total": len(CWE_TOP_25), "details": results}


def evaluate_mitre(model_name: str) -> dict:
    """Evaluate against MITRE ATT&CK mapping."""
    print(f"[EVAL] MITRE ATT&CK ({len(MITRE_TECHNIQUES)} cases)...")
    correct = 0
    results = []

    for case in MITRE_TECHNIQUES:
        prompt = f"Given this scenario, identify the MITRE ATT&CK technique:\n\n{case['scenario']}\n\nTechnique ID (e.g., T1234):"
        response = query_model(model_name, prompt)

        found = case["technique"].lower() in response or case["expected"].lower() in response
        if found:
            correct += 1

        results.append({
            "technique": case["technique"],
            "found": found,
            "response": response[:100],
        })

    score = (correct / len(MITRE_TECHNIQUES)) * 100
    print(f"[EVAL] MITRE Score: {score:.1f}% ({correct}/{len(MITRE_TECHNIQUES)})")
    return {"score": score, "correct": correct, "total": len(MITRE_TECHNIQUES), "details": results}


def evaluate_code_review(model_name: str) -> dict:
    """Evaluate code review capability."""
    print(f"[EVAL] Code Review ({len(CODE_REVIEW_CASES)} cases)...")
    correct = 0
    total_findings = 0
    results = []

    for case in CODE_REVIEW_CASES:
        prompt = f"Review this {case['language']} code for security vulnerabilities:\n\n```{case['language']}\n{case['code']}\n```\n\nList vulnerabilities found:"
        response = query_model(model_name, prompt)

        findings_found = 0
        for finding in case["expected_findings"]:
            if finding.lower() in response:
                findings_found += 1

        if findings_found > 0:
            correct += 1
        total_findings += findings_found / len(case["expected_findings"])

        results.append({
            "language": case["language"],
            "findings": findings_found,
            "expected": len(case["expected_findings"]),
            "severity": case["severity"],
            "response": response[:150],
        })

    score = (total_findings / len(CODE_REVIEW_CASES)) * 100
    print(f"[EVAL] Code Review Score: {score:.1f}%")
    return {"score": score, "cases_passed": correct, "total": len(CODE_REVIEW_CASES), "details": results}


def main():
    parser = argparse.ArgumentParser(description="AEGIS Security Benchmark Evaluation")
    parser.add_argument("--model", default="aegis", help="Ollama model name")
    parser.add_argument("--benchmarks", default="all", help="Comma-separated: cwe,mitre,code-review")
    parser.add_argument("--output", default="results.json", help="Output JSON file")
    args = parser.parse_args()

    benchmarks = args.benchmarks.split(",")
    results = {"model": args.model, "benchmarks": {}}

    if "all" in benchmarks or "cwe" in benchmarks:
        results["benchmarks"]["cwe_top25"] = evaluate_cwe(args.model)

    if "all" in benchmarks or "mitre" in benchmarks:
        results["benchmarks"]["mitre_attack"] = evaluate_mitre(args.model)

    if "all" in benchmarks or "code-review" in benchmarks:
        results["benchmarks"]["code_review"] = evaluate_code_review(args.model)

    # Overall score
    scores = [v["score"] for v in results["benchmarks"].values()]
    results["overall_score"] = sum(scores) / len(scores) if scores else 0

    print(f"\n{'='*50}")
    print(f"AEGIS OVERALL SCORE: {results['overall_score']:.1f}%")
    print(f"{'='*50}")

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[EVAL] Results saved to: {args.output}")


if __name__ == "__main__":
    main()
