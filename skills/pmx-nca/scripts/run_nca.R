#!/usr/bin/env Rscript
# Noncompartmental analysis with PKNCA, single-dose, one row per concentration record.
# Writes individual (long) and per-group mean results. Deterministic: same input + options -> same bytes.
suppressPackageStartupMessages({
  library(optparse)
  library(PKNCA)
})

opts <- list(
  make_option("--input", help = "CSV with concentration (and optionally dosing) records [required]"),
  make_option("--outdir", default = ".", help = "Output directory [default %default]"),
  make_option("--prefix", default = "nca_results", help = "Output file prefix [default %default]"),
  make_option("--group", default = "DRUG", help = "Grouping column, e.g. drug/study/dose group; '' for none [default %default]"),
  make_option("--subject", default = "USUBJID", help = "Subject column [default %default]"),
  make_option("--time", default = "ATPTN", help = "Time since dose column [default %default]"),
  make_option("--conc", default = "AVAL", help = "Concentration column [default %default]"),
  make_option("--dose", default = "DOSE", help = "Dose amount column [default %default]"),
  make_option("--route", default = "ROUTE", help = "Route column; '' if all subjects share --route-default [default %default]"),
  make_option("--route-iv", default = "1,IV,iv,intravascular,intravenous", help = "Values of --route meaning IV bolus"),
  make_option("--route-default", default = "extravascular", help = "Route when no route column: intravascular|extravascular"),
  make_option("--evid", default = "EVID", help = "Event id column (0 = observation); '' if file has only observations"),
  make_option("--blq", default = "BLQ", help = "BLQ flag column (1 = BLQ); '' to treat conc == 0 as BLQ"),
  make_option("--blq-rule", default = "zero-before-tmax-missing-after",
              help = "zero-before-tmax-missing-after | zero | missing | pknca-default [default %default]"),
  make_option("--auc-method", default = "lin-up/log-down", help = "lin-up/log-down | linear [default %default]"),
  make_option("--lambda-rule", default = "adjr2", help = "adjr2 (best adjusted R2, PKNCA) [default %default]"),
  make_option("--adjr2-factor", type = "double", default = 1e-4,
              help = "Tolerance favouring more points when adj R2 ties (PKNCA adj.r.squared.factor) [default %default]"),
  make_option("--min-points", type = "integer", default = 3, help = "Min points for lambda_z [default %default]"),
  make_option("--min-r2", type = "double", default = 1e-6,
              help = "Min R2 for lambda_z to be reported (tiny default = report all; filter downstream on Rsq_adjusted) [default %default]"),
  make_option("--allow-tmax-in-lambda", action = "store_true", default = FALSE, help = "Allow Tmax point in lambda_z fit"),
  make_option("--id-style", default = "separate", help = "separate: GROUP + USUBJID columns | combined: GROUP_USUBJID in first column")
)
a <- parse_args(OptionParser(option_list = opts, description = "PKNCA single-dose NCA"))
if (is.null(a$input)) stop("--input is required")

`%||%` <- function(x, y) if (is.null(x) || identical(x, "")) y else x
has <- function(col) !identical(col, "") && !is.null(col)

d <- read.csv(a$input, stringsAsFactors = FALSE, check.names = FALSE, na.strings = c("", ".", "NA"))
need <- c(a$subject, a$time, a$conc, a$dose)
if (has(a$group)) need <- c(need, a$group)
miss <- setdiff(need, names(d))
if (length(miss)) stop("missing columns: ", paste(miss, collapse = ", "), "\navailable: ", paste(names(d), collapse = ", "))

grp <- if (has(a$group)) as.character(d[[a$group]]) else "ALL"
d$.grp <- grp
d$.sub <- as.character(d[[a$subject]])
d$.time <- as.numeric(d[[a$time]])
d$.conc <- suppressWarnings(as.numeric(d[[a$conc]]))
d$.dose <- as.numeric(d[[a$dose]])
iv_vals <- trimws(strsplit(a$`route-iv`, ",")[[1]])
d$.route <- if (has(a$route) && a$route %in% names(d)) {
  ifelse(as.character(d[[a$route]]) %in% iv_vals, "intravascular", "extravascular")
} else a$`route-default`
is_obs <- if (has(a$evid) && a$evid %in% names(d)) as.numeric(d[[a$evid]]) == 0 else rep(TRUE, nrow(d))
d$.blq <- if (has(a$blq) && a$blq %in% names(d)) {
  f <- suppressWarnings(as.numeric(d[[a$blq]])); !is.na(f) & f == 1
} else !is.na(d$.conc) & d$.conc == 0

obs <- d[is_obs & !is.na(d$.time), ]
obs <- obs[order(obs$.grp, obs$.sub, obs$.time), ]
key <- paste(obs$.grp, obs$.sub, sep = "\r")

# ---- BLQ handling (applied here, explicitly, so the rule is visible and auditable) ----
rule <- a$`blq-rule`
obs$.conc[obs$.blq] <- 0
if (rule == "zero-before-tmax-missing-after") {
  keep <- unlist(lapply(split(seq_len(nrow(obs)), factor(key, levels = unique(key))), function(i) {
    cc <- obs$.conc[i]
    if (all(is.na(cc) | cc == 0)) return(rep(TRUE, length(i)))
    itmax <- which.max(replace(cc, is.na(cc), -Inf))
    !(obs$.blq[i] & seq_along(i) > itmax)   # BLQ after Tmax -> missing (dropped)
  }))
  obs <- obs[keep, ]
} else if (rule == "missing") {
  obs <- obs[!obs$.blq, ]
} else if (rule == "zero") {
  # keep all BLQ as 0
} else if (rule != "pknca-default") stop("unknown --blq-rule: ", rule)
obs <- obs[!is.na(obs$.conc), ]

# ---- dose table: one single dose at time 0 per subject ----
dose_src <- if (has(a$evid) && a$evid %in% names(d)) d[!is_obs, ] else d
dose_src <- dose_src[!is.na(dose_src$.dose), ]
dose_src <- dose_src[!duplicated(paste(dose_src$.grp, dose_src$.sub, sep = "\r")), ]
doses <- data.frame(.grp = dose_src$.grp, .sub = dose_src$.sub, .dose = dose_src$.dose,
                    .time = if (has(a$evid) && a$evid %in% names(d)) dose_src$.time else 0,
                    .route = dose_src$.route, stringsAsFactors = FALSE)
doses$.time[is.na(doses$.time)] <- 0
doses$.duration <- 0
route_of <- setNames(doses$.route, paste(doses$.grp, doses$.sub, sep = "\r"))

# ---- IV bolus without an observed C0: log-linear back-extrapolation from first two points ----
add_c0 <- list()
for (k in unique(key[key %in% names(route_of)[route_of == "intravascular"]])) {
  i <- which(paste(obs$.grp, obs$.sub, sep = "\r") == k)
  if (!length(i) || any(obs$.time[i] == 0)) next
  t <- obs$.time[i][1:2]; cc <- obs$.conc[i][1:2]
  c0 <- if (length(i) >= 2 && all(cc > 0) && cc[2] < cc[1]) exp(log(cc[1]) - (log(cc[2]) - log(cc[1])) / (t[2] - t[1]) * t[1]) else cc[1]
  r <- obs[i[1], ]; r$.time <- 0; r$.conc <- c0; r$.blq <- FALSE
  add_c0[[k]] <- r
}
if (length(add_c0)) {
  obs <- rbind(obs, do.call(rbind, add_c0))
  obs <- obs[order(obs$.grp, obs$.sub, obs$.time), ]
  message("back-extrapolated C0 for ", length(add_c0), " IV subject(s)")
}

# ---- PKNCA ----
PKNCA.options(default = TRUE)
suppressWarnings(PKNCA.options(
  auc.method = switch(a$`auc-method`, "lin-up/log-down" = "lin up/log down", linear = "linear",
                      stop("unknown --auc-method")),
  adj.r.squared.factor = a$`adjr2-factor`,
  min.hl.points = a$`min-points`,
  min.hl.r.squared = a$`min-r2`,
  allow.tmax.in.half.life = a$`allow-tmax-in-lambda`,
  conc.blq = if (rule == "pknca-default") list(first = "keep", middle = "drop", last = "keep")
             else list(first = "keep", middle = "keep", last = "keep")
))
cobj <- PKNCAconc(obs, .conc ~ .time | .grp + .sub)
dobj <- PKNCAdose(doses, .dose ~ .time | .grp + .sub, route = ".route", duration = ".duration")
iv <- data.frame(start = 0, end = Inf, cmax = TRUE, tmax = TRUE, auclast = TRUE, aucinf.obs = TRUE,
                 half.life = TRUE, adj.r.squared = TRUE, lambda.z.n.points = TRUE, cl.obs = TRUE, vz.obs = TRUE)
res <- suppressWarnings(as.data.frame(pk.nca(PKNCAdata(cobj, dobj, intervals = iv))))

# ---- output ----
map <- c(cmax = "Cmax", tmax = "Tmax", auclast = "AUClast", aucinf.obs = "AUCINF_obs",
         half.life = "HL_Lambda_z", adj.r.squared = "Rsq_adjusted", lambda.z.n.points = "No_points_lambda_z",
         cl.obs = "CL_obs", vz.obs = "Vz_obs")
res <- res[res$PPTESTCD %in% names(map) & !is.na(res$PPORRES), ]
rk <- paste(res$.grp, res$.sub, sep = "\r")
ev <- route_of[rk] == "extravascular"
code <- unname(map[res$PPTESTCD])
code[ev & code == "CL_obs"] <- "CLF_obs"
code[ev & code == "Vz_obs"] <- "VzF_obs"
out <- data.frame(GROUP = res$.grp, USUBJID = res$.sub, PPTESTCD = code, PPSTRESN = res$PPORRES,
                  ROUTE = ifelse(ev, "extravascular", "intravascular"), stringsAsFactors = FALSE)
ord <- c("Cmax", "Tmax", "AUClast", "AUCINF_obs", "HL_Lambda_z", "CL_obs", "CLF_obs", "Vz_obs", "VzF_obs",
         "Rsq_adjusted", "No_points_lambda_z")
sub_num <- suppressWarnings(as.numeric(out$USUBJID))
out <- out[order(out$GROUP, if (all(!is.na(sub_num))) sub_num else out$USUBJID, match(out$PPTESTCD, ord)), ]
gname <- if (has(a$group)) a$group else "GROUP"

indiv <- if (a$`id-style` == "combined") {
  x <- data.frame(paste(out$GROUP, out$USUBJID, sep = "_"), out$PPTESTCD, out$PPSTRESN); names(x) <- c(gname, "PPTESTCD", "PPSTRESN"); x
} else { x <- out; names(x)[1] <- gname; x }
mean_df <- aggregate(PPSTRESN ~ GROUP + PPTESTCD, data = out, FUN = function(v) c(mean = mean(v), n = length(v)))
mean_df <- data.frame(mean_df[1:2], PPSTRESN = mean_df$PPSTRESN[, "mean"], N = mean_df$PPSTRESN[, "n"])
mean_df <- mean_df[order(mean_df$GROUP, match(mean_df$PPTESTCD, ord)), ]
names(mean_df)[1] <- gname

dir.create(a$outdir, showWarnings = FALSE, recursive = TRUE)
f_ind <- file.path(a$outdir, paste0(a$prefix, "_individual.csv"))
f_mean <- file.path(a$outdir, paste0(a$prefix, "_mean.csv"))
write.csv(indiv, f_ind, row.names = FALSE)
write.csv(mean_df, f_mean, row.names = FALSE)
settings <- c(sprintf("PKNCA %s", packageVersion("PKNCA")), sprintf("auc_method=%s", a$`auc-method`),
              sprintf("lambda_rule=%s adjr2_factor=%g min_points=%d min_r2=%g allow_tmax=%s", a$`lambda-rule`,
                      a$`adjr2-factor`, a$`min-points`, a$`min-r2`, a$`allow-tmax-in-lambda`),
              sprintf("blq_rule=%s", rule), sprintf("subjects=%d records_used=%d c0_extrapolated=%d",
                                                     length(unique(rk)), nrow(obs), length(add_c0)))
writeLines(settings, file.path(a$outdir, paste0(a$prefix, "_settings.txt")))
cat("wrote", f_ind, "\nwrote", f_mean, "\n", paste(settings, collapse = "\n"), "\n")
