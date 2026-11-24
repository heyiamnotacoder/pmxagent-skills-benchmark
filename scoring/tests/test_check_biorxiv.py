"""paper/check_biorxiv.py: the gate that keeps an unfinished PDF off bioRxiv (paper/SPEC.md slice S14, issue #16).
Run: python3 -m unittest discover -s scoring/tests"""
import os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "paper"))
import check_biorxiv as cb  # noqa: E402

TEX = r"""\documentclass{article}
\usepackage{lineno}
\linenumbers
\begin{document}
\includegraphics[width=\linewidth]{figures/fig_a.pdf}
Text. % \TODO in a comment is fine
\end{document}
"""
LOG_OK = "This is pdfTeX\nOutput written on main.pdf (20 pages, 1 bytes).\n"


class Gate(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.d, "figures"))
        open(os.path.join(self.d, "figures", "fig_a.pdf"), "w").close()

    def problems(self, tex=TEX, log=LOG_OK):
        return cb.problems(tex, log, self.d)

    def test_clean_build_passes(self):
        self.assertEqual(self.problems(), [])

    def test_todo_in_text_fails(self):
        self.assertTrue(self.problems(tex=TEX.replace("Text.", r"Text \TODO{cite}.")))

    def test_undefined_reference_or_citation_fails(self):
        for line in ("LaTeX Warning: Reference `fig:x' on page 3 undefined on input line 9.",
                     "LaTeX Warning: Citation `smith2020' on page 2 undefined on input line 4.",
                     "LaTeX Warning: There were undefined references."):
            self.assertTrue(self.problems(log=LOG_OK + line + "\n"), line)

    def test_stale_cross_references_fail(self):
        self.assertTrue(self.problems(log=LOG_OK + "LaTeX Warning: Label(s) may have changed. Rerun to get "
                                                    "cross-references right.\n"))

    def test_missing_figure_fails(self):
        os.remove(os.path.join(self.d, "figures", "fig_a.pdf"))
        self.assertTrue(self.problems())
        self.assertTrue(self.problems(log=LOG_OK + "! LaTeX Error: File `figures/fig_b.pdf' not found.\n"))

    def test_line_numbers_must_stay_on(self):
        self.assertTrue(self.problems(tex=TEX.replace("\\linenumbers\n", "")))


if __name__ == "__main__":
    unittest.main()
