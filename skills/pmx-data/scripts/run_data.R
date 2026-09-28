#!/usr/bin/env Rscript
# Standardise PK data (long CSV, wide CSV, NONMEM, Excel) to an ADPC-like long table:
#   USUBJID, GROUP, EVID, ATPTN, AVAL, AVALU, DOSE, DOSEU, ROUTE, BLQ
# BLQ strings ("BLQ", "<LLOQ", "<0.5", "BQL", "ND") -> AVAL 0 + BLQ = 1. Writes a QC report of every change.
suppressPackageStartupMessages({
  library(optparse)
})

opts <- list(
  make_option("--input", help = "csv/tsv/txt/xlsx/xls [required]"),
  make_option("--sheet", default = "1", help = "Excel sheet name or index [default %default]"),
  make_option("--format", default = "auto", help = "auto | long | wide | nonmem [default %default]"),
  make_option("--subject", default = "", help = "Subject column (auto-detected if empty)"),
  make_option("--group", default = "", help = "Group column (drug/study/dose group), optional"),
  make_option("--time", default = "", help = "Time column (long) (auto-detected if empty)"),
  make_option("--conc", default = "", help = "Concentration column (long) (auto-detected if empty)"),
  make_option("--time-cols", default = "", help = "Wide: regex selecting time columns; the number in each name is the time [default: numeric-looking names]"),
  make_option("--dose", default = "", help = "Dose column, or a number applied to all subjects"),
  make_option("--route", default = "", help = "Route column, or a value applied to all (1/IV = intravascular, 2/PO/SC = extravascular)"),
  make_option("--conc-unit", default = "", help = "Concentration unit if not in the data (e.g. ng/mL)"),
  make_option("--unit-col", default = "", help = "Column holding concentration units, if any"),
  make_option("--dose-unit", default = "mg", help = "[default %default]"),
  make_option("--to-unit", default = "", help = "Convert all concentrations to this mass/volume unit (e.g. ug/mL). Off by default."),
  make_option("--outdir", default = ".", help = "[default %default]"),
  make_option("--prefix", default = "adpc", help = "[default %default]")
)
a <- parse_args(OptionParser(option_list = opts, description = "Standardise PK data to ADPC-like long format"))
if (is.null(a$input)) stop("--input is required")
qc <- character()
note <- function(...) qc <<- c(qc, sprintf(...))

# ---- read ----
ext <- tolower(tools::file_ext(a$input))
d <- if (ext %in% c("xlsx", "xls")) {
  sh <- suppressWarnings(as.integer(a$sheet)); as.data.frame(readxl::read_excel(a$input, sheet = if (is.na(sh)) a$sheet else sh, col_types = "text"))
} else {
  first <- readLines(a$input, n = 1)
  sep <- if (grepl("\t", first)) "\t" else if (grepl(",", first)) "," else if (grepl(";", first)) ";" else ""
  read.table(a$input, header = TRUE, sep = sep, stringsAsFactors = FALSE, check.names = FALSE, colClasses = "character",
             na.strings = c("", "NA"), comment.char = "", quote = "\"", strip.white = TRUE)
}
names(d) <- trimws(sub("^#", "", names(d)))
note("read %s: %d rows x %d cols", basename(a$input), nrow(d), ncol(d))

pick <- function(given, candidates) {
  if (nzchar(given)) { if (!given %in% names(d)) stop("column not found: ", given, "; available: ", paste(names(d), collapse = ", ")); return(given) }
  hit <- names(d)[toupper(names(d)) %in% toupper(candidates)]
  if (length(hit)) hit[1] else ""
}
u <- toupper(names(d))
fmt <- a$format
if (fmt == "auto") fmt <- if (all(c("ID", "TIME", "DV") %in% u) && any(c("AMT", "EVID", "MDV") %in% u)) "nonmem" else
  if (sum(grepl("^[A-Za-z_]*[0-9.]+[A-Za-z_]*$", names(d)) & !grepl("ID$", u)) >= 3 && pick(a$time, c("TIME", "ATPTN", "NTIME", "TAD", "TIME_H")) == "") "wide" else "long"
note("format: %s", fmt)

num <- function(x) suppressWarnings(as.numeric(gsub(",", "", x)))
blq_parse <- function(x) {
  s <- trimws(as.character(x))
  isblq <- !is.na(s) & grepl("^(<|BLQ|BQL|LLOQ|<LLOQ|ND|NQ|BLOQ|BELOW)", toupper(s))
  v <- num(s); v[isblq] <- 0
  bad <- !is.na(s) & !isblq & is.na(v) & !s %in% c(".", "")
  list(val = v, blq = as.integer(isblq), bad = bad)
}

subj <- pick(a$subject, c("USUBJID", "SUBJID", "ID", "SUBJECT", "PATIENT", "PTID"))
if (!nzchar(subj)) stop("could not find a subject column; use --subject")
grp <- pick(a$group, c("GROUP", "DRUG", "TRT", "ARM", "COHORT", "DOSEGRP", "STUDY"))

if (fmt == "nonmem") {
  ev <- if ("EVID" %in% u) num(d[[names(d)[u == "EVID"][1]]]) else ifelse(num(d[[names(d)[u == "MDV"][1]]]) == 1 & "AMT" %in% u & num(d[[names(d)[u == "AMT"][1]]]) > 0, 1, 0)
  tcol <- names(d)[u == "TIME"][1]; dv <- names(d)[u == "DV"][1]
  amt <- if ("AMT" %in% u) num(d[[names(d)[u == "AMT"][1]]]) else NA
  p <- blq_parse(d[[dv]])
  if ("BLQ" %in% u) p$blq <- pmax(p$blq, num(d[[names(d)[u == "BLQ"][1]]]), na.rm = TRUE)
  long <- data.frame(USUBJID = d[[subj]], GROUP = if (nzchar(grp)) d[[grp]] else "", EVID = ev, ATPTN = num(d[[tcol]]),
                     AVAL = ifelse(ev == 1, NA, p$val), BLQ = ifelse(ev == 1, NA, p$blq), .dose_row = amt,
                     .unit = if (nzchar(a$`unit-col`)) d[[a$`unit-col`]] else a$`conc-unit`, stringsAsFactors = FALSE)
  if ("CMT" %in% u && !nzchar(a$route)) {
    cm <- num(d[[names(d)[u == "CMT"][1]]])
    dose_cmt <- tapply(cm[ev == 1], d[[subj]][ev == 1], function(x) x[1])
    obs_cmt <- tapply(cm[ev == 0], d[[subj]][ev == 0], function(x) x[1])
    long$.route_cmt <- ifelse(dose_cmt[long$USUBJID] == obs_cmt[long$USUBJID], "1", "2")
    note("route inferred from CMT: dose into observation compartment = IV (1), else extravascular (2)")
  }
  p_bad <- p$bad & ev != 1
} else if (fmt == "wide") {
  tc <- if (nzchar(a$`time-cols`)) grep(a$`time-cols`, names(d), value = TRUE) else
    names(d)[grepl("[0-9]", names(d)) & !toupper(names(d)) %in% toupper(c(subj, grp, a$dose, a$route, a$`unit-col`))]
  if (length(tc) < 2) stop("could not identify time columns; use --time-cols")
  tt <- num(sub("^[^0-9.]*([0-9.]+).*$", "\\1", tc))
  note("wide: %d time columns -> times %s", length(tc), paste(tt, collapse = ","))
  rows <- lapply(seq_len(nrow(d)), function(i) {
    p <- blq_parse(unlist(d[i, tc]))
    data.frame(USUBJID = d[[subj]][i], GROUP = if (nzchar(grp)) d[[grp]][i] else "", EVID = 0, ATPTN = tt, AVAL = p$val,
               BLQ = p$blq, .bad = p$bad, .rowi = i, stringsAsFactors = FALSE)
  })
  long <- do.call(rbind, rows)
  long$.unit <- if (nzchar(a$`unit-col`)) d[[a$`unit-col`]][long$.rowi] else a$`conc-unit`
  p_bad <- long$.bad
} else {
  tcol <- pick(a$time, c("ATPTN", "TIME", "NTIME", "TAD", "AFRLT", "TIME_H", "HOUR", "HOURS"))
  ccol <- pick(a$conc, c("AVAL", "CONC", "DV", "CONCENTRATION", "PCSTRESN", "PCORRES", "RESULT"))
  if (!nzchar(tcol) || !nzchar(ccol)) stop("could not find time/conc columns; use --time/--conc")
  ev <- if ("EVID" %in% u) num(d[[names(d)[u == "EVID"][1]]]) else rep(0, nrow(d))
  p <- blq_parse(d[[ccol]])
  if ("BLQ" %in% u) { f <- num(d[[names(d)[u == "BLQ"][1]]]); p$blq <- pmax(p$blq, ifelse(is.na(f), 0, f)); p$val[p$blq == 1] <- 0 }
  ucol <- if (nzchar(a$`unit-col`)) a$`unit-col` else pick("", c("AVALU", "UNIT", "UNITS", "CONCU", "PCSTRESU"))
  long <- data.frame(USUBJID = d[[subj]], GROUP = if (nzchar(grp)) d[[grp]] else "", EVID = ev, ATPTN = num(d[[tcol]]),
                     AVAL = ifelse(ev == 1, NA, p$val), BLQ = ifelse(ev == 1, NA, p$blq),
                     .unit = if (nzchar(ucol)) d[[ucol]] else a$`conc-unit`, stringsAsFactors = FALSE)
  p_bad <- p$bad & ev != 1
}
if (any(p_bad)) note("WARNING: %d non-numeric concentration values set to missing", sum(p_bad))
note("BLQ strings/flags -> AVAL 0, BLQ=1: %d records", sum(long$BLQ == 1, na.rm = TRUE))

# ---- dose and route (per subject) ----
dose_of <- function() {
  if (nzchar(a$dose) && !is.na(num(a$dose))) return(setNames(rep(num(a$dose), length(unique(long$USUBJID))), unique(long$USUBJID)))
  dc <- if (nzchar(a$dose)) a$dose else pick("", c("DOSE", "AMT", "DOSEA", "EXDOSE"))
  if (fmt == "nonmem" && !is.null(long$.dose_row)) { x <- long[long$EVID == 1, ]; return(tapply(x$.dose_row, x$USUBJID, function(v) v[1])) }
  if (!nzchar(dc)) return(NULL)
  tapply(num(d[[dc]]), d[[subj]], function(v) v[!is.na(v) & v > 0][1])
}
doses <- dose_of()
long$DOSE <- if (is.null(doses)) NA else as.numeric(doses[as.character(long$USUBJID)])
if (is.null(doses)) note("WARNING: no dose information found (CL/Vz will not be computable)")
long$DOSEU <- a$`dose-unit`
rt <- if (nzchar(a$route) && !a$route %in% names(d)) rep(a$route, nrow(long)) else {
  rc <- if (nzchar(a$route)) a$route else pick("", c("ROUTE", "EXROUTE", "RTE"))
  if (nzchar(rc)) as.character(tapply(d[[rc]], d[[subj]], function(v) v[!is.na(v)][1])[as.character(long$USUBJID)])
  else if (!is.null(long$.route_cmt)) long$.route_cmt else rep(NA, nrow(long))
}
rtu <- toupper(trimws(rt))
long$ROUTE <- ifelse(rtu %in% c("1", "IV", "INTRAVENOUS", "INTRAVASCULAR", "IVB", "BOLUS"), 1,
                ifelse(is.na(rtu), NA, 2))
if (any(is.na(long$ROUTE))) note("WARNING: route missing for %d subjects", length(unique(long$USUBJID[is.na(long$ROUTE)])))

# ---- units ----
long$AVALU <- long$.unit
if (nzchar(a$`to-unit`)) {
  mass <- c(PG = 1e-12, NG = 1e-9, UG = 1e-6, MCG = 1e-6, MG = 1e-3, G = 1)
  vol <- c(ML = 1e-3, DL = 1e-1, L = 1)
  fac <- function(unit) {
    s <- toupper(gsub("µ|μ", "U", trimws(unit))); pr <- strsplit(s, "/")[[1]]
    if (length(pr) != 2 || !pr[1] %in% names(mass) || !pr[2] %in% names(vol)) return(NA)
    mass[[pr[1]]] / vol[[pr[2]]]
  }
  f_to <- fac(a$`to-unit`); if (is.na(f_to)) stop("--to-unit must be mass/volume, e.g. ng/mL")
  uu <- unique(long$AVALU[!is.na(long$AVALU)])
  for (x in uu) {
    f <- fac(x)
    if (is.na(f)) { note("WARNING: cannot convert unit '%s' (molar/IU needs MW or activity) - left unchanged", x); next }
    i <- long$AVALU == x & !is.na(long$AVALU)
    long$AVAL[i] <- long$AVAL[i] * f / f_to; long$AVALU[i] <- a$`to-unit`
    note("unit %s -> %s: x%g (%d records)", x, a$`to-unit`, f / f_to, sum(i))
  }
}

# ---- dose records, QC, write ----
obs <- long[long$EVID == 0, ]
obs <- obs[!is.na(obs$ATPTN), ]
dup <- duplicated(obs[, c("USUBJID", "GROUP", "ATPTN")])
if (any(dup)) note("WARNING: %d duplicate subject/time records (kept, please review)", sum(dup))
if (any(obs$AVAL < 0, na.rm = TRUE)) note("WARNING: %d negative concentrations", sum(obs$AVAL < 0, na.rm = TRUE))
first <- obs[!duplicated(obs[, c("USUBJID", "GROUP")]), ]
dose_rows <- transform(first, EVID = 1, ATPTN = 0, AVAL = NA, BLQ = NA)
out <- rbind(dose_rows, obs)[, c("USUBJID", "GROUP", "EVID", "ATPTN", "AVAL", "AVALU", "DOSE", "DOSEU", "ROUTE", "BLQ")]
sn <- suppressWarnings(as.numeric(out$USUBJID))
out <- out[order(out$GROUP, if (all(!is.na(sn))) sn else out$USUBJID, out$ATPTN, -out$EVID), ]
if (!nzchar(grp)) out$GROUP <- NULL
note("output: %d subjects, %d observation records, %d dose records", nrow(first), nrow(obs), nrow(dose_rows))

dir.create(a$outdir, showWarnings = FALSE, recursive = TRUE)
f <- file.path(a$outdir, paste0(a$prefix, ".csv"))
write.csv(out, f, row.names = FALSE, na = ".")
writeLines(qc, file.path(a$outdir, paste0(a$prefix, "_qc.txt")))
cat("wrote", f, "\n", paste(qc, collapse = "\n"), "\n")
