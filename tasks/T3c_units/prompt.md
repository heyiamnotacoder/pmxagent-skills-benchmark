Please perform noncompartmental analysis on `nca_units.csv` (concentration units differ between drugs, see AVALU; doses are in mg; ATPTN is hours post-dose). Report individual and mean AUClast, AUCINF_obs, HL_Lambda_z, Cmax, Tmax, CL_obs (or CLF_obs for extravascular), Vz_obs (or VzF_obs for extravascular), Rsq_adjusted and No_points_lambda_z.

**Report all results in harmonised units:** concentrations in ug/mL, AUC in h*ug/mL, clearance in L/h, volume in L, half-life in h.

Notes:
(1) Use adjusted R2 for terminal point selection and lambda_z estimation
(2) Route of administration (ROUTE) of 1 is intravenous and 2 is extravascular
(3) Use Linear Up Log Down trapezoidal rule

Individual results file: columns DRUG, PPTESTCD, PPSTRESN, where DRUG is `<drug>_<subject number>` (e.g. `abatacept_1`).
