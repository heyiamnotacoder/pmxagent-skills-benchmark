#!/usr/bin/env Rscript
# Population PK simulation (1/2/3-compartment; IV bolus, IV infusion, first-order oral/SC) with mrgsolve.
# Log-normal between-subject variability, optional residual error, fixed seed -> reproducible output.
suppressPackageStartupMessages({
  library(optparse)
  library(mrgsolve)
})

opts <- list(
  make_option("--model", default = "2cmt", help = "1cmt | 2cmt | 3cmt [default %default]"),
  make_option("--route", default = "iv-bolus", help = "iv-bolus | iv-infusion | oral (first-order absorption; also SC) [default %default]"),
  make_option("--params", default = NULL,
              help = "Typical values, e.g. 'CL=0.2,V1=3.6,Q=0.75,V2=2.8' (V1 central, V2/V3 peripheral, Q/Q3 intercompartmental, KA, F)"),
  make_option("--preset", default = NULL, help = "Parameter preset instead of --params: mab-davda2014 (70 kg typical mAb)"),
  make_option("--per-kg", action = "store_true", default = FALSE, help = "--params CL/Q/V are per kg; multiplied by --bw"),
  make_option("--bw", type = "double", default = 70, help = "Body weight, kg [default %default]"),
  make_option("--doses", default = NULL, help = "Comma list of dose levels (one group each) [required]"),
  make_option("--dose-unit", default = "mg", help = "[default %default]"),
  make_option("--n-per-group", type = "integer", default = 20, help = "[default %default]"),
  make_option("--ii", type = "double", default = 0, help = "Dosing interval (0 = single dose) [default %default]"),
  make_option("--n-doses", type = "integer", default = 1, help = "Total number of doses [default %default]"),
  make_option("--dur", type = "double", default = 1, help = "Infusion duration (iv-infusion) [default %default]"),
  make_option("--end", type = "double", default = NULL, help = "Simulation end time [required]"),
  make_option("--times", default = NULL, help = "Explicit comma list of sampling times (overrides --delta)"),
  make_option("--delta", type = "double", default = NULL, help = "Sampling step (default: end/100)"),
  make_option("--time-unit", default = "h", help = "h | day — unit of all times and rate constants [default %default]"),
  make_option("--bsv", type = "double", default = 0, help = "Between-subject CV (e.g. 0.3 = 30%%), log-normal [default %default]"),
  make_option("--bsv-params", default = "CL,V1,Q,V2,Q3,V3,KA", help = "Params that get BSV [default %default]"),
  make_option("--ruv-prop", type = "double", default = 0, help = "Proportional residual error CV [default %default]"),
  make_option("--ruv-add", type = "double", default = 0, help = "Additive residual error SD [default %default]"),
  make_option("--seed", type = "integer", default = 42, help = "[default %default]"),
  make_option("--outdir", default = ".", help = "[default %default]"),
  make_option("--prefix", default = "pk_simulation", help = "[default %default]"),
  make_option("--plot", default = "TRUE", help = "Write PNG of profiles (TRUE/FALSE) [default %default]")
)
a <- parse_args(OptionParser(option_list = opts, description = "mrgsolve population PK simulation"))
if (is.null(a$doses) || is.null(a$end)) stop("--doses and --end are required")

parse_kv <- function(s) {
  kv <- strsplit(trimws(strsplit(s, ",")[[1]]), "=")
  setNames(as.numeric(vapply(kv, `[`, "", 2)), toupper(trimws(vapply(kv, `[`, "", 1))))
}
# Davda et al. MAbs 2014;6:1094 (via nlmixr2lib PK_2cmt_mAb_Davda_2014), 70 kg, time unit = day
presets <- list(`mab-davda2014` = list(p = c(CL = 0.200, V1 = 3.61, Q = 0.747, V2 = 2.75, KA = 0.282, F = 0.744),
                                       unit = "day", model = "2cmt"))
if (!is.null(a$preset)) {
  pr <- presets[[a$preset]]; if (is.null(pr)) stop("unknown preset: ", a$preset)
  p <- pr$p
  if (a$`time-unit` == "h" && pr$unit == "day") p[c("CL", "Q", "KA")] <- p[c("CL", "Q", "KA")] / 24
  if (!is.null(a$params)) { over <- parse_kv(a$params); p[names(over)] <- over }
} else {
  if (is.null(a$params)) stop("give --params or --preset")
  p <- parse_kv(a$params)
}
if (a$`per-kg`) for (n in intersect(names(p), c("CL", "V1", "Q", "V2", "Q3", "V3"))) p[n] <- p[n] * a$bw

need <- switch(a$model, "1cmt" = c("CL", "V1"), "2cmt" = c("CL", "V1", "Q", "V2"),
               "3cmt" = c("CL", "V1", "Q", "V2", "Q3", "V3"), stop("unknown --model"))
if (a$route == "oral") need <- c(need, "KA")
miss <- setdiff(need, names(p)); if (length(miss)) stop("missing params for ", a$model, "/", a$route, ": ", paste(miss, collapse = ","))
if (!"F" %in% names(p) || a$route != "oral") p["F"] <- 1
if (!"KA" %in% names(p)) p["KA"] <- 1

# our names -> mrgsolve modlib names
modname <- c("1cmt" = "pk1cmt", "2cmt" = "pk2cmt", "3cmt" = "pk3cmt")[[a$model]]
rename <- switch(a$model,
  "1cmt" = c(CL = "CL", V1 = "V", KA = "KA"),
  "2cmt" = c(CL = "CL", V1 = "V2", Q = "Q", V2 = "V3", KA = "KA"),
  "3cmt" = c(CL = "CL", V1 = "V2", Q = "Q3", V2 = "V3", Q3 = "Q4", V3 = "V4", KA = "KA"))
mod <- suppressMessages(modlib(modname, quiet = TRUE))

set.seed(a$seed)
doses <- as.numeric(strsplit(a$doses, ",")[[1]])
N <- length(doses) * a$`n-per-group`
idata <- data.frame(ID = seq_len(N), DOSE = rep(doses, each = a$`n-per-group`),
                    DOSEGRP = rep(seq_along(doses), each = a$`n-per-group`))
omega <- sqrt(log(1 + a$bsv^2))          # log-normal SD giving the requested CV
bsvp <- intersect(toupper(trimws(strsplit(a$`bsv-params`, ",")[[1]])), need)
for (n in names(rename)) {
  typ <- p[[n]]
  eta <- if (n %in% bsvp && a$bsv > 0) rnorm(N, 0, omega) else 0
  idata[[rename[[n]]]] <- typ * exp(eta)
}
idata$F_ <- p[["F"]]

cmt <- if (a$route == "oral") "EV" else "CENT"
ev <- data.frame(ID = idata$ID, time = 0, amt = idata$DOSE * idata$F_, cmt = cmt, evid = 1,
                 ii = a$ii, addl = if (a$ii > 0) a$`n-doses` - 1 else 0,
                 rate = if (a$route == "iv-infusion") idata$DOSE / a$dur else 0)
times <- if (!is.null(a$times)) as.numeric(strsplit(a$times, ",")[[1]]) else
  seq(0, a$end, by = if (is.null(a$delta)) a$end / 100 else a$delta)

out <- as.data.frame(mrgsim_df(mod, data = ev, idata = idata[, c("ID", unname(rename))], tgrid = times,
                               obsonly = TRUE, recsort = 3))
out <- merge(out[, c("ID", "time", "CP")], idata[, c("ID", "DOSE", "DOSEGRP")], by = "ID")
out <- out[order(out$ID, out$time), ]
if (a$`ruv-prop` > 0 || a$`ruv-add` > 0) {
  out$CP <- out$CP * (1 + rnorm(nrow(out), 0, a$`ruv-prop`)) + rnorm(nrow(out), 0, a$`ruv-add`)
  out$CP[out$CP < 0] <- 0
}
conc_unit <- paste0(a$`dose-unit`, "/L")
res <- data.frame(USUBJID = out$ID, DOSEGRP = out$DOSEGRP, DOSE = out$DOSE, DOSEU = a$`dose-unit`,
                  TIME = out$time, TIMEU = a$`time-unit`, CONC = signif(out$CP, 10), CONCU = conc_unit,
                  ROUTE = a$route)

dir.create(a$outdir, showWarnings = FALSE, recursive = TRUE)
f_csv <- file.path(a$outdir, paste0(a$prefix, ".csv"))
write.csv(res, f_csv, row.names = FALSE)
ip <- idata[, c("ID", "DOSE", unname(rename))]; names(ip) <- c("USUBJID", "DOSE", names(rename))
write.csv(ip, file.path(a$outdir, paste0(a$prefix, "_individual_params.csv")), row.names = FALSE)
settings <- c(sprintf("mrgsolve %s model=%s route=%s", packageVersion("mrgsolve"), a$model, a$route),
              sprintf("typical: %s", paste(names(p), signif(p, 6), sep = "=", collapse = ", ")),
              sprintf("per_kg=%s bw=%g time_unit=%s", a$`per-kg`, a$bw, a$`time-unit`),
              sprintf("doses=%s n_per_group=%d ii=%g n_doses=%d end=%g n_times=%d", a$doses, a$`n-per-group`, a$ii,
                      a$`n-doses`, a$end, length(times)),
              sprintf("bsv_cv=%g (omega=%.4f) on %s; ruv_prop=%g ruv_add=%g; seed=%d", a$bsv, omega,
                      paste(bsvp, collapse = ","), a$`ruv-prop`, a$`ruv-add`, a$seed))
writeLines(settings, file.path(a$outdir, paste0(a$prefix, "_settings.txt")))

if (toupper(a$plot) == "TRUE") {
  suppressPackageStartupMessages(library(ggplot2))
  res$Dose <- factor(paste(res$DOSE, a$`dose-unit`), levels = paste(doses, a$`dose-unit`))
  g <- ggplot(res[res$CONC > 0, ], aes(TIME, CONC, group = USUBJID, colour = Dose)) +
    geom_line(alpha = 0.5) + scale_y_log10() + theme_bw() +
    labs(x = paste0("Time (", a$`time-unit`, ")"), y = paste0("Concentration (", conc_unit, ")"),
         title = sprintf("%s %s, %d/group, BSV CV %g%%", a$model, a$route, a$`n-per-group`, 100 * a$bsv))
  ggsave(file.path(a$outdir, paste0(a$prefix, ".png")), g, width = 7, height = 4.5, dpi = 120)
}
cat("wrote", f_csv, "\n", paste(settings, collapse = "\n"), "\n")
