Please conduct the following analysis:

(1) Simulate the PK of 60 subjects (20 per group) at the following dose levels: 10, 30, and 100 mg over 4 weeks using a two-compartment IV bolus model with 30% between-subject variability. Plot the results.

(2) Take the simulated PK profiles for each subject and conduct NCA to determine the individual AUCs (0-last). Please report the average AUC (0-last), Cmax, and half-life for each group as a table.

(3) Conduct an ER analysis using the individual AUCs (0-last) for exposure and a binary response variable. Use response rates of 0.1, 0.5, and 0.9 for the 10, 30, and 100 mg groups, respectively.

When finished, also write `output/results.json` with keys: `group_summary` (list of objects with dose_mg, mean_AUClast, mean_Cmax, mean_half_life), `ec50` (number, exposure units), `ec50_units`, `seed` (or null), `n_timepoints_per_subject`, `pk_parameters` (typical values used), and `files` (paths of the simulated data, NCA results and ER data you produced).
