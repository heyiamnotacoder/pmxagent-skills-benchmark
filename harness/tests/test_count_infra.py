"""Tests for the infrastructure footprint count (count_infra.py, paper/SPEC.md slice S9, issue #11).
Run: python3 -m unittest discover -s harness/tests"""
import hashlib, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import count_infra as ci


class Category(unittest.TestCase):
    """Each maintained file falls into exactly one category of the table; docs and licences are not counted."""
    def test_skills(self):
        self.assertEqual(ci.category("Skills", "pmx-nca/scripts/run_nca.R"), "tool")
        self.assertEqual(ci.category("Skills", "pmx-library/scripts/Makevars.rxode2"), "tool")
        self.assertEqual(ci.category("Skills", "pmx-nca/tests/test_run_nca.R"), "tests")
        self.assertEqual(ci.category("Skills", "pmx-nca/SKILL.md"), "instructions")
        self.assertEqual(ci.category("Skills", "FROZEN.sha256"), "other")

    def test_pmxagent(self):
        for p in ("apis/endpoints/nca.R", "apis/models/1CM.cpp", "apis/utils/units.R"):
            self.assertEqual(ci.category("PMxAgent", p), "tool", p)
        for p in ("server.py", "apis/rapi.R", "docker/Dockerfile.rapi", "docker/r-packages.txt", "docker-compose.yml",
                  "docker-compose.ghcr.yml", ".mcp.json", ".dockerignore", "requirements.txt",
                  ".github/workflows/test.yml"):
            self.assertEqual(ci.category("PMxAgent", p), "serving", p)
        for p in ("apis/tests/test_nca.R", "tests/test_endpoints.py", "tests/conftest.py", "pytest.ini",
                  "requirements-dev.txt"):
            self.assertEqual(ci.category("PMxAgent", p), "tests", p)
        self.assertEqual(ci.category("PMxAgent", "CLAUDE.md"), "instructions")
        for p in ("README.md", "CONTRIBUTING.md", "CLA.md", "CITATION.cff", ".gitignore"):
            self.assertEqual(ci.category("PMxAgent", p), "other", p)


COMPOSE = """# comment
networks:
  pmxnet:
    driver: bridge

services:
  rapi:
    build:
      context: .
    ports:
      - "5762:8000"
    networks:
      - pmxnet

  mcp:
    ports:
      - "8000:8000"
    environment:
      A: "1"
volumes:
  shared:
"""
OVERLAY = """services:
  rapi:
    image: x
  mcp:
    image: y
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def freeze(sk):
    """skills/FROZEN.sha256 as `shasum -a 256` writes it from the skills folder (`<hash>  ./<path>`)."""
    lines = []
    for d, _, names in sorted(os.walk(sk)):
        for f in sorted(names):
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                lines.append(f"{hashlib.sha256(fh.read()).hexdigest()}  ./{os.path.relpath(p, sk)}\n")
    write(os.path.join(sk, "FROZEN.sha256"), "".join(lines))


class Compose(unittest.TestCase):
    def test_containers_and_host_ports_from_base_and_overlay(self):
        with tempfile.TemporaryDirectory() as d:
            write(os.path.join(d, "docker-compose.yml"), COMPOSE)
            write(os.path.join(d, "docker-compose.ghcr.yml"), OVERLAY)
            self.assertEqual(ci.compose(d), {"container": ["mcp", "rapi"], "port": ["5762:8000", "8000:8000"]})

    def test_port_syntax_it_cannot_read_stops_the_count(self):
        for ports in ('    ports: ["8000:8000"]\n', "    ports:\n      - target: 8000\n        published: 8000\n"):
            with tempfile.TemporaryDirectory() as d:
                write(os.path.join(d, "docker-compose.yml"), "services:\n  mcp:\n" + ports)
                with self.assertRaises(ValueError, msg=ports):
                    ci.compose(d)


class Footprint(unittest.TestCase):
    """rows() -> one row per counted item; summary() -> the table's numbers. Lines are non-blank, non-comment."""
    def test_two_small_stacks(self):
        with tempfile.TemporaryDirectory() as d:
            sk, pmx = os.path.join(d, "skills"), os.path.join(d, "pmx")
            write(os.path.join(sk, "pmx-nca", "SKILL.md"), "# NCA\n\nUse the script.\n")
            write(os.path.join(sk, "pmx-nca", "scripts", "run.R"), "# header\nx <- 1\n\n  # note\ny <- 2\n")
            write(os.path.join(sk, "pmx-nca", "tests", "test_run.R"), "expect_true(TRUE)\n")
            freeze(sk)
            write(os.path.join(pmx, "server.py"), "import x\n# c\nrun()\n")
            write(os.path.join(pmx, "apis", "endpoints", "nca.R"), "#* @post /NCA\nf <- function() 1\n")
            write(os.path.join(pmx, "apis", "models", "1CM.cpp"), "// model\nint a;\n")
            write(os.path.join(pmx, "docker", "Dockerfile.rapi"), "# base\nFROM r\nRUN x\n")
            write(os.path.join(pmx, "docker-compose.yml"), COMPOSE)
            write(os.path.join(pmx, "tests", "test_e.py"), "def test(): pass\n")
            write(os.path.join(pmx, "CLAUDE.md"), "# Guide\nline\n")
            write(os.path.join(pmx, "README.md"), "# Readme\n" * 50)
            write(os.path.join(pmx, "data", ".gitkeep"), "")
            s = ci.summary(ci.rows(sk, pmx))
        compose_lines = sum(1 for l in COMPOSE.splitlines() if l.strip() and not l.lstrip().startswith("#"))
        self.assertEqual(s["Skills"], {"service": 0, "container": 0, "port": 0, "setup": 3,
                                       "tool": 2, "serving": 0, "tests": 1, "instructions": 2, "lines": 5})
        serving = 2 + 2 + compose_lines
        self.assertEqual(s["PMxAgent"], {"service": 3, "container": 2, "port": 2, "setup": 4, "tool": 2,
                                         "serving": serving, "tests": 1, "instructions": 2, "lines": 5 + serving})

    def test_without_pmxagent_repo_only_skills(self):
        with tempfile.TemporaryDirectory() as d:
            sk = os.path.join(d, "skills")
            write(os.path.join(sk, "a", "SKILL.md"), "x\n")
            freeze(sk)
            s = ci.summary(ci.rows(sk, os.path.join(d, "missing")))
        self.assertEqual(set(s), {"Skills"})

    def test_skills_that_differ_from_the_freeze_are_not_counted(self):
        """The paper counts the frozen Skills: a changed or an unfrozen file stops the count."""
        for change in ("edit", "add"):
            with tempfile.TemporaryDirectory() as d:
                sk = os.path.join(d, "skills")
                write(os.path.join(sk, "a", "SKILL.md"), "x\n")
                freeze(sk)
                write(os.path.join(sk, "a", "SKILL.md" if change == "edit" else "scripts/new.R"), "y\n")
                with self.assertRaises(ValueError, msg=change):
                    ci.rows(sk, os.path.join(d, "missing"))


if __name__ == "__main__":
    unittest.main()
