#!/usr/bin/env Rscript
# Published popPK model library (nlmixr2lib) + simulation (rxode2).
#   run_library.R list [--search TEXT]
#   run_library.R show  --model NAME
#   run_library.R simulate --model NAME --dose 100 --end 56 [...]
here <- dirname(normalizePath(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)[1])))
if (!nzchar(Sys.getenv("R_MAKEVARS_USER"))) Sys.setenv(R_MAKEVARS_USER = file.path(here, "Makevars.rxode2"))
suppressPackageStartupMessages({
  library(optparse)
  library(nlmixr2lib)
})

opts <- list(
  make_option("--search", default = "", help = "list: case-insensitive text/regex over name + description"),
  make_option("--model", default = "", help = "show/simulate: model name from 'list'"),
  make_option("--dose", type = "double", default = NA, help = "Dose amount (model dosing units)"),
  make_option("--cmt", default = "", help = "Dosing compartment (default: first of the model's dosing cmts; e.g. depot, central)"),
  make_option("--dur", type = "double", default = 0, help = "Infusion duration (0 = bolus) [default %default]"),
  make_option("--ii", type = "double", default = 0, help = "Dosing interval [default %default]"),
  make_option("--n-doses", type = "integer", default = 1, help = "[default %default]"),
  make_option("--end", type = "double", default = NA, help = "Simulation end time (model time unit)"),
  make_option("--times", default = "", help = "Explicit sampling times (comma list)"),
  make_option("--n", type = "integer", default = 100, help = "Subjects [default %default]"),
  make_option("--covariates", default = "", help = "Fixed covariates, e.g. 'WT=70,AGE=45'"),
  make_option("--no-iiv", action = "store_true", default = FALSE, help = "Typical-value simulation (no between-subject variability)"),
  make_option("--seed", type = "integer", default = 42, help = "[default %default]"),
  make_option("--outdir", default = ".", help = "[default %default]"),
  make_option("--prefix", default = "library_sim", help = "[default %default]")
)
p <- OptionParser(option_list = opts, usage = "%prog list|show|simulate [options]")
args <- parse_args(p, positional_arguments = 1)
cmd <- args$args[1]; a <- args$options
db <- nlmixr2lib::modeldb

model_info <- function(name) {
  if (!name %in% db$name) stop("unknown model '", name, "'. Use: list --search <text>")
  f <- readModelDb(name)
  src <- deparse(body(f))
  grab <- function(key) { l <- grep(paste0("^\\s*", key, "\\s*(<-|=)"), src, value = TRUE); if (length(l)) trimws(sub(".*?(<-|=)\\s*", "", l[1])) else "" }
  list(f = f, reference = gsub('^"|"$', "", grab("reference")), units = grab("units"), row = db[db$name == name, ])
}

if (cmd == "list") {
  x <- db
  if (nzchar(a$search)) x <- x[grepl(a$search, paste(x$name, x$description), ignore.case = TRUE), ]
  cat(sprintf("%d of %d models (nlmixr2lib %s)\n", nrow(x), nrow(db), packageVersion("nlmixr2lib")))
  for (i in seq_len(nrow(x))) cat(sprintf("%s | %s | params: %s | dosing: %s\n", x$name[i], x$description[i], x$parameters[i], x$dosing[i]))
} else if (cmd == "show") {
  mi <- model_info(a$model)
  cat("name:", a$model, "\ndescription:", mi$row$description, "\nreference:", mi$reference, "\nunits:", mi$units,
      "\ndosing compartments:", mi$row$dosing, "\nDV:", mi$row$DV, "\n\n")
  suppressPackageStartupMessages(library(rxode2))
  ui <- suppressMessages(rxode2::rxode2(mi$f))
  cat("covariates required:", if (length(ui$allCovs)) paste(ui$allCovs, collapse = ", ") else "none", "\n\n")
  ini <- ui$iniDf[, c("name", "est", "fix", "label")]; ini$est <- signif(ini$est, 5)
  print(ini, row.names = FALSE)
  cat("\nmodel:\n"); print(mi$f)
} else if (cmd == "simulate") {
  suppressPackageStartupMessages(library(rxode2))
  if (is.na(a$dose) || (is.na(a$end) && !nzchar(a$times))) stop("simulate needs --dose and --end (or --times)")
  mi <- model_info(a$model)
  ui <- suppressMessages(rxode2::rxode2(mi$f))
  covs <- ui$allCovs
  cv <- if (nzchar(a$covariates)) { kv <- strsplit(strsplit(a$covariates, ",")[[1]], "="); setNames(as.numeric(vapply(kv, `[`, "", 2)), trimws(vapply(kv, `[`, "", 1))) } else numeric()
  miss <- setdiff(covs, names(cv))
  if (length(miss)) stop("model needs covariates: ", paste(miss, collapse = ", "), " -> pass --covariates 'NAME=value,...'")
  cmt <- if (nzchar(a$cmt)) a$cmt else trimws(strsplit(mi$row$dosing, ",")[[1]][1])
  times <- if (nzchar(a$times)) as.numeric(strsplit(a$times, ",")[[1]]) else seq(0, a$end, length.out = 101)
  dose_args <- list(amt = a$dose, cmt = cmt)
  if (a$ii > 0) dose_args <- c(dose_args, ii = a$ii, addl = a$`n-doses` - 1)
  if (a$dur > 0) dose_args$dur <- a$dur
  ev <- do.call(et, dose_args) |> et(times)
  if (a$`no-iiv`) ui <- rxode2::zeroRe(ui)
  prm <- if (length(cv)) as.data.frame(as.list(cv)) else NULL
  s <- suppressMessages(rxSolve(ui, ev, params = prm, nSub = if (a$`no-iiv`) 1 else a$n, seed = a$seed, addDosing = FALSE))
  d <- as.data.frame(s)
  dv <- mi$row$DV
  idc <- intersect(c("sim.id", "id"), names(d))[1]
  out <- data.frame(ID = if (is.na(idc)) 1 else d[[idc]], TIME = d$time, IPRED = d[[dv]],
                    DV_SIM = if ("sim" %in% names(d)) d$sim else d[[dv]])
  dir.create(a$outdir, showWarnings = FALSE, recursive = TRUE)
  write.csv(out, file.path(a$outdir, paste0(a$prefix, ".csv")), row.names = FALSE)
  q <- do.call(rbind, lapply(split(out$IPRED, out$TIME), function(v) quantile(v, c(0.05, 0.5, 0.95), na.rm = TRUE)))
  summ <- data.frame(TIME = as.numeric(rownames(q)), P05 = q[, 1], MEDIAN = q[, 2], P95 = q[, 3])
  write.csv(summ, file.path(a$outdir, paste0(a$prefix, "_summary.csv")), row.names = FALSE)
  png(file.path(a$outdir, paste0(a$prefix, ".png")), width = 840, height = 540, res = 110)
  matplot(summ$TIME, summ[, c("P05", "MEDIAN", "P95")], type = "l", lty = c(2, 1, 2), col = 1, xlab = "Time",
          ylab = dv, main = sprintf("%s: %g x%d into %s (n=%d)", a$model, a$dose, a$`n-doses`, cmt, length(unique(out$ID))))
  invisible(dev.off())
  settings <- c(sprintf("nlmixr2lib %s rxode2 %s", packageVersion("nlmixr2lib"), packageVersion("rxode2")),
                sprintf("model=%s reference=%s units=%s", a$model, mi$reference, mi$units),
                sprintf("dose=%g cmt=%s dur=%g ii=%g n_doses=%d n=%d iiv=%s seed=%d covariates=%s", a$dose, cmt, a$dur,
                        a$ii, a$`n-doses`, length(unique(out$ID)), !a$`no-iiv`, a$seed, a$covariates))
  writeLines(settings, file.path(a$outdir, paste0(a$prefix, "_settings.txt")))
  cat(paste(settings, collapse = "\n"), "\n"); print(head(summ, 5), row.names = FALSE)
} else stop("command must be list, show or simulate")
