"""Port the validated Terminal-Bench test fixes to harbor-framework/terminal-bench.

TB2 fixes go to legacy/<task>/; TB4 fixes (audit/disclosures-tb4, `tb4-` commands) go to tasks/<task>/ with a minor
version bump in task.toml, as CONTRIBUTING asks for verifier changes.

    python3 tools/upstream_prs.py prepare <clone>     # patched task copies in results/upstream-tasks/
    audit/disclosures/repro.sh with TB2=results/upstream-tasks   # reference must score 1, wrong solutions 0
    python3 tools/upstream_prs.py branches <clone>    # one branch + commit per task in the clone
    python3 tools/upstream_prs.py finish <clone> <task> <pr-number>   # fill the PR number into the changelog
    python3 tools/upstream_prs.py tb4-prepare <clone>  /  tb4-branches <clone>   # same, for TASKS_TB4

<clone> is a checkout of your fork of harbor-framework/terminal-bench (sparse is fine) on its main branch.
The PR description is written by hand, as the repo's PR template asks.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DISC = REPO / "audit" / "disclosures"
DISC_TB4 = REPO / "audit" / "disclosures-tb4"
OUT = REPO / "results" / "upstream-tasks"
OUT_TB4 = REPO / "results" / "upstream-tasks-tb4"
AUTHOR = ["-c", "user.name=Ishan Nerlekar", "-c", "user.email=ishan.nerlekar@gmail.com"]
PR_URL = "https://github.com/harbor-framework/terminal-bench/pull/"

# task: (changelog sentence, commit subject). configure-git-webserver and modernize-scientific-stack are
# skipped: terminal-bench-2-1 PR #37 and terminal-bench PR #2464 already fix them.
TASKS = {
    "prove-plus-comm": ("Updated verifier to reject proofs that depend on axioms or admitted lemmas.",
                        "reject proofs that depend on axioms or admitted lemmas"),
    "git-leak-recovery": ("Updated verifier to search every stored object for the secret and to require the original commit messages.",
                          "search every stored object for the secret; require original commit messages"),
    "regex-log": ("Updated verifier samples so invalid-date lines have a valid IP, and added February 29, May and octet 250 cases.",
                  "make invalid-date samples test the date; cover Feb 29, May and octet 250"),
    "db-wal-recovery": ("Updated verifier to check that SQLite reads all records once the WAL is fixed.",
                        "check that the WAL file is actually fixed"),
    "cobol-modernization": ("Updated verifier to check that an invalid sale leaves the data files unchanged.",
                            "check that an invalid sale leaves the data files unchanged"),
    "sparql-university": ("Updated oracle to count students per department, and verifier to cover a non-EU country, a 10-student department and students split across departments.",
                          "count students per department; cover non-EU, exactly-10 and split-department cases"),
    "headless-terminal": ("Updated verifier to check that the shell accepts a new command after Ctrl-C.",
                          "check that Ctrl-C actually frees the shell"),
    "openssl-selfsigned-cert": ("Updated verifier to check key permissions, the certificate subject, self-signing, and that the PEM holds server.key and server.crt.",
                                "check key mode, subject fields, self-signing and the PEM's key pair"),
    "torch-pipeline-parallelism": ("Updated verifier to require a backward pass on every stage and to check the AFAB order in time.",
                                   "require backward passes and check AFAB order in time"),
    "torch-tensor-parallelism": ("Updated verifier to use a non-zero bias in the forward and backward checks.",
                                 "check outputs and gradients with a non-zero bias"),
}

# TB4 (tasks/): issue number, changelog sentence, commit subject. Validated with repro.sh --fixed: reference 1, wrong 0.
TASKS_TB4 = {
    "intrastat-meldung": (2731, "Updated verifier to check the staged declaration reference on M-019 and M-067.",
                          "check staged references on M-019 and M-067"),
    "react-lead-form": (2734, "Updated verifier to check holidays in the business clock.",
                        "check holidays in the business clock"),
    "vba-userform-port": (2732, "Updated verifier with a trace that edits and saves a customer through frmCustomers.",
                          "add a frmCustomers form trace"),
}


def apply_fix(task: str, dst: Path) -> None:
    src = DISC / task
    if (patch := src / "test_fix.patch").exists():  # paths look like a/<task>/tests/test_outputs.py
        subprocess.run(["patch", "-s", "-p2", "-d", str(dst), "-i", str(patch)], check=True)
    else:
        tests = dst / "tests" / "test_outputs.py"
        text = tests.read_text().rstrip("\n")
        for add in sorted(src.glob("test_fix_addition*.py")):
            text += "\n\n\n" + add.read_text().strip("\n")
        tests.write_text(text + "\n")
    if task == "sparql-university":  # the reference query itself counts across departments
        solve = dst / "solution" / "solve.sh"
        s = solve.read_text()
        start, end = s.index("PREFIX"), s.rindex("EOF")
        solve.write_text(s[:start] + (src / "solution_fix.sparql").read_text().rstrip("\n") + "\n" + s[end:])


def add_changelog(readme: Path, sentence: str) -> None:
    text = readme.read_text()
    assert "## Change Log" not in text, f"{readme} already has a changelog; add the bullet by hand"
    title, _, rest = text.partition("\n")
    readme.write_text(f"{title}\n\n## Change Log\n\n- [#TBD]({PR_URL}TBD) {sentence}\n{rest}")


def prepare(clone: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for task, (sentence, _) in TASKS.items():
        dst = OUT / task
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(clone / "legacy" / task, dst)
        apply_fix(task, dst)
        add_changelog(dst / "README.md", sentence)
        compile(Path(dst / "tests" / "test_outputs.py").read_text(), task, "exec")  # syntax check
        print(f"prepared {task}")


def git(clone: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(clone), *AUTHOR, *args], check=True, capture_output=True, text=True).stdout


def branches(clone: Path) -> None:
    base = git(clone, "rev-parse", "--abbrev-ref", "HEAD").strip()
    for task, (_, subject) in TASKS.items():
        branch = f"fix/{task}-verifier"
        git(clone, "checkout", "-q", "-B", branch, base)
        target = clone / "legacy" / task
        shutil.rmtree(target)
        shutil.copytree(OUT / task, target)
        git(clone, "add", "-A", f"legacy/{task}")
        git(clone, "commit", "-q", "-m", f"fix({task}): {subject}")
        print(f"{branch}: {git(clone, 'log', '-1', '--format=%h %s').strip()}")
    git(clone, "checkout", "-q", base)


def bump_minor(toml: Path) -> str:
    text = toml.read_text()
    m = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"$', text, re.M)
    new = f"{m[1]}.{int(m[2]) + 1}.0"
    toml.write_text(text[:m.start()] + f'version = "{new}"' + text[m.end():])
    return new


def tb4_prepare(clone: Path) -> None:
    OUT_TB4.mkdir(parents=True, exist_ok=True)
    for task, (_, sentence, _) in TASKS_TB4.items():
        dst = OUT_TB4 / task
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(clone / "tasks" / task, dst)
        subprocess.run(["patch", "-s", "-p2", "-d", str(dst), "-i", str(DISC_TB4 / task / "test_fix.patch")], check=True)
        version = bump_minor(dst / "task.toml")
        readme = dst / "README.md"
        text = readme.read_text()
        head = "## Change Log\n\n"
        assert text.count(head) == 1, f"{readme}: expected one '## Change Log' section"
        readme.write_text(text.replace(head, f"{head}- [#TBD]({PR_URL}TBD) `{version}` {sentence}\n\n"))
        print(f"prepared {task} {version}")


def tb4_branches(clone: Path) -> None:
    base = git(clone, "rev-parse", "--abbrev-ref", "HEAD").strip()
    for task, (_, _, subject) in TASKS_TB4.items():
        branch = f"fix/{task}-verifier"
        git(clone, "checkout", "-q", "-B", branch, base)
        target = clone / "tasks" / task
        shutil.rmtree(target)
        shutil.copytree(OUT_TB4 / task, target)
        git(clone, "add", "-A", f"tasks/{task}")
        git(clone, "commit", "-q", "-m", f"fix({task}): {subject}")
        print(f"{branch}: {git(clone, 'log', '-1', '--format=%h %s').strip()}")
    git(clone, "checkout", "-q", base)


def finish(clone: Path, task: str, number: str) -> None:
    git(clone, "checkout", "-q", f"fix/{task}-verifier")
    readme = clone / ("tasks" if task in TASKS_TB4 else "legacy") / task / "README.md"
    readme.write_text(readme.read_text().replace("[#TBD](" + PR_URL + "TBD)", f"[#{number}]({PR_URL}{number})"))
    git(clone, "commit", "-q", "-am", "Add PR number to changelog")  # a new commit: no force-push needed
    print(f"updated; now: git -C {clone} push origin fix/{task}-verifier")


if __name__ == "__main__":
    cmd, clone = sys.argv[1], Path(sys.argv[2]).expanduser().resolve()
    {"prepare": lambda: prepare(clone), "branches": lambda: branches(clone),
     "finish": lambda: finish(clone, sys.argv[3], sys.argv[4]),
     "tb4-prepare": lambda: tb4_prepare(clone), "tb4-branches": lambda: tb4_branches(clone)}[cmd]()
