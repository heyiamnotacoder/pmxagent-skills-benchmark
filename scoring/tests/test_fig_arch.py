"""Fig 1 (paper/figures/fig_arch.tex) stays in step with the data figures and the manuscript (issue #12).

Run: python3 -m unittest discover -s scoring/tests
"""
import os, re, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import figures

PAPER = os.path.join(os.path.dirname(os.path.dirname(HERE)), "paper")


def read(*p):
    with open(os.path.join(PAPER, *p), encoding="utf-8") as fh:
        return fh.read()


class ArchFigure(unittest.TestCase):
    def test_arm_colours_match_the_data_figures_and_every_arm_has_a_text_label(self):
        tex = read("figures", "fig_arch.tex")
        defined = {a: h.lower() for a, h in re.findall(r"\\definecolor\{arm(\w+)\}\{HTML\}\{([0-9A-Fa-f]{6})\}", tex)}
        self.assertEqual(defined, {a: c.lstrip("#").lower() for a, c in figures.COLOR.items()})
        for arm in figures.ARMS:   # colour is never the only cue: each arm's chip carries its name
            self.assertRegex(tex, r"\\armchip\{" + arm + r"\}")

    def test_fig_arch_is_figure_1_and_is_cited_before_it_appears(self):
        tex = read("main.tex")
        figs = re.findall(r"\\begin\{figure\}.*?\\end\{figure\}", tex, flags=re.S)
        self.assertIn(r"\includegraphics", figs[0])
        self.assertIn("figures/fig_arch.pdf", figs[0])
        self.assertIn(r"\label{fig:arch}", figs[0])
        self.assertLess(tex.index(r"\ref{fig:arch}"), tex.index(figs[0]))


if __name__ == "__main__":
    unittest.main()
