The Excel workbook `pk_raw.xlsx` contains single-dose PK data from 30 drugs, one sheet per drug (sheet name = drug). Each row is a patient; time columns give hours post-dose; `<LLOQ` means below the limit of quantification; blank cells were not sampled.

Please perform noncompartmental analysis and report the individual and mean PK parameters for each patient/drug: AUClast, AUCINF_obs, HL_Lambda_z, Cmax, Tmax, CL_obs (or CLF_obs for extravascular), Vz_obs (or VzF_obs for extravascular), adjusted R2 (Rsq_adjusted), and number of terminal timepoints (No_points_lambda_z).

Notes:
(1) Use adjusted R2 for terminal point selection and lambda_z estimation
(2) DO NOT perform any unit conversions
(3) Use Linear Up Log Down trapezoidal rule

Individual results file: columns DRUG, PPTESTCD, PPSTRESN, where DRUG is `<drug>_<subject number>` (e.g. `abatacept_1`). Subject number = the number in the Patient ID (P007 -> 7).
