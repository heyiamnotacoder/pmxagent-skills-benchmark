#!/usr/bin/env Rscript
# Exposure-response analysis: binary (logistic) or continuous (linear / Emax / sigmoid Emax / Imax), AIC model selection.
# Reads exposure directly from a file (e.g. pmx-nca individual output) so values are never re-typed.
suppressPackageStartupMessages({
  library(optparse)
})

opts <- list(
  make_option("--input", help = "CSV with one row per subject (wide) or pmx-nca long output [required]"),
  make_option("--exposure", default = "AUClast", help = "Exposure column, or PPTESTCD if --input is NCA long format [default %default]"),
  make_option("--subject", default = "USUBJID", help = "[default %default]"),
  make_option("--group", default = "", help = "Group column (e.g. DOSEGRP, DOSE) [default none]"),
  make_option("--response", default = "", help = "Response column; omit to generate binary data with --response-rates"),
  make_option("--type", default = "binary", help = "binary | continuous [default %default]"),
  make_option("--response-rates", default = "", help = "Generate binary response: 'group:rate,...' e.g. '1:0.1,2:0.5,3:0.9'"),
  make_option("--rate-mode", default = "exact", help = "exact: round(rate*n) responders per group | bernoulli: independent draws [default %default]"),
  make_option("--models", default = "", help = "Candidates. binary: logistic,logistic-log  continuous: linear,emax,sigmoid-emax,imax [default all]"),
  make_option("--seed", type = "integer", default = 42, help = "[default %default]"),
  make_option("--outdir", default = ".", help = "[default %default]"),
  make_option("--prefix", default = "er", help = "[default %default]"),
  make_option("--plot", default = "TRUE", help = "[default %default]")
)
a <- parse_args(OptionParser(option_list = opts, description = "Exposure-response analysis"))
if (is.null(a$input)) stop("--input is required")

d <- read.csv(a$input, stringsAsFactors = FALSE, check.names = FALSE)
if (all(c("PPTESTCD", "PPSTRESN") %in% names(d))) {          # NCA long format -> one row per subject
  idcols <- setdiff(names(d), c("PPTESTCD", "PPSTRESN", "ROUTE", "N"))
  e <- d[d$PPTESTCD == a$exposure, ]
  if (!nrow(e)) stop("PPTESTCD '", a$exposure, "' not found; available: ", paste(unique(d$PPTESTCD), collapse = ", "))
  d <- e[, idcols, drop = FALSE]; d[[a$exposure]] <- e$PPSTRESN
}
for (col in c(a$exposure, a$subject, if (nzchar(a$group)) a$group))
  if (!col %in% names(d)) stop("missing column: ", col, "; available: ", paste(names(d), collapse = ", "))
d$E <- as.numeric(d[[a$exposure]])
d$G <- if (nzchar(a$group)) as.character(d[[a$group]]) else "ALL"
d <- d[order(suppressWarnings(as.numeric(d$G)), d$G, suppressWarnings(as.numeric(d[[a$subject]])), d[[a$subject]]), ]

set.seed(a$seed)
if (nzchar(a$response)) {
  d$Y <- as.numeric(d[[a$response]])
} else {
  if (a$type != "binary" || !nzchar(a$`response-rates`)) stop("give --response, or --type binary with --response-rates")
  kv <- strsplit(strsplit(a$`response-rates`, ",")[[1]], ":")
  rates <- setNames(as.numeric(vapply(kv, `[`, "", 2)), trimws(vapply(kv, `[`, "", 1)))
  if (!all(unique(d$G) %in% names(rates))) stop("--response-rates must cover groups: ", paste(unique(d$G), collapse = ","))
  d$Y <- 0
  for (g in unique(d$G)) {
    i <- which(d$G == g)
    if (a$`rate-mode` == "exact") d$Y[sample(i, round(rates[[g]] * length(i)))] <- 1
    else d$Y[i] <- rbinom(length(i), 1, rates[[g]])
  }
}
d <- d[is.finite(d$E) & !is.na(d$Y), ]

fits <- list()
cand <- if (nzchar(a$models)) trimws(strsplit(a$models, ",")[[1]]) else
  if (a$type == "binary") c("logistic", "logistic-log") else c("linear", "emax", "sigmoid-emax", "imax")

if (a$type == "binary") {
  for (m in cand) {
    f <- switch(m, logistic = glm(Y ~ E, binomial, d), "logistic-log" = glm(Y ~ log(E), binomial, d[d$E > 0, ]),
                stop("unknown binary model: ", m))
    cf <- summary(f)$coefficients
    b0 <- cf[1, 1]; b1 <- cf[2, 1]
    ec50 <- if (m == "logistic") -b0 / b1 else exp(-b0 / b1)
    # delta-method SE for EC50
    g <- if (m == "logistic") c(-1 / b1, b0 / b1^2) else ec50 * c(-1 / b1, b0 / b1^2)
    se50 <- sqrt(drop(t(g) %*% vcov(f) %*% g))
    fits[[m]] <- list(fit = f, aic = AIC(f), n = nobs(f),
      par = data.frame(term = c("intercept", if (m == "logistic") "slope_E" else "slope_logE", "EC50"),
                       estimate = c(b0, b1, ec50), se = c(cf[1, 2], cf[2, 2], se50),
                       p = c(cf[1, 4], cf[2, 4], NA)))
  }
} else {
  emax_starts <- function() {
    e50 <- quantile(d$E, c(0.25, 0.5, 0.75), names = FALSE); rng <- diff(range(d$Y))
    expand.grid(E0 = min(d$Y), EMAX = c(0.5, 1, 2) * rng, EC50 = e50, H = c(1, 2))
  }
  fit_nls <- function(form, starts, lower) {
    best <- NULL
    for (i in seq_len(nrow(starts))) {
      f <- tryCatch(nls(form, d, start = as.list(starts[i, ]), algorithm = "port", lower = lower,
                        control = nls.control(maxiter = 500, warnOnly = FALSE)), error = function(e) NULL)
      if (!is.null(f) && (is.null(best) || deviance(f) < deviance(best) - 1e-12)) best <- f
    }
    best
  }
  for (m in cand) {
    st <- emax_starts()
    f <- switch(m,
      linear = lm(Y ~ E, d),
      emax = fit_nls(Y ~ E0 + EMAX * E / (EC50 + E), unique(st[, c("E0", "EMAX", "EC50")]), c(-Inf, -Inf, 1e-12)),
      "sigmoid-emax" = fit_nls(Y ~ E0 + EMAX * E^H / (EC50^H + E^H), st, c(-Inf, -Inf, 1e-12, 0.1)),
      imax = fit_nls(Y ~ E0 * (1 - IMAX * E / (IC50 + E)),
                     unique(data.frame(E0 = max(d$Y), IMAX = c(0.5, 0.9), IC50 = rep(quantile(d$E, c(.25, .5, .75)), each = 2))),
                     c(-Inf, 0, 1e-12)),
      stop("unknown continuous model: ", m))
    if (is.null(f)) { message("model ", m, " did not converge"); next }
    cf <- summary(f)$coefficients
    fits[[m]] <- list(fit = f, aic = AIC(f), n = nobs(f),
      par = data.frame(term = rownames(cf), estimate = cf[, 1], se = cf[, 2], p = cf[, 4]),
      pred = local({ ff <- f; function(x) predict(ff, data.frame(E = x)) }))
  }
}
if (!length(fits)) stop("no model converged")

aics <- vapply(fits, `[[`, 0, "aic")
sel <- names(which.min(aics))
tab <- do.call(rbind, lapply(names(fits), function(m) cbind(model = m, fits[[m]]$par, AIC = fits[[m]]$aic,
                                                           n = fits[[m]]$n, selected = m == sel)))
rownames(tab) <- NULL
grid <- seq(min(d$E), max(d$E), length.out = 200)
pr <- if (a$type == "binary") predict(fits[[sel]]$fit, data.frame(E = grid), type = "response") else fits[[sel]]$pred(grid)
summ <- do.call(rbind, lapply(split(d, d$G), function(x) data.frame(group = x$G[1], n = nrow(x),
  mean_exposure = mean(x$E), sd_exposure = sd(x$E), mean_response = mean(x$Y))))

dir.create(a$outdir, showWarnings = FALSE, recursive = TRUE)
out <- d[, c(a$subject, if (nzchar(a$group)) a$group), drop = FALSE]; out[[a$exposure]] <- d$E; out$RESPONSE <- d$Y
write.csv(out, file.path(a$outdir, paste0(a$prefix, "_data.csv")), row.names = FALSE)
write.csv(tab, file.path(a$outdir, paste0(a$prefix, "_parameters.csv")), row.names = FALSE)
write.csv(summ, file.path(a$outdir, paste0(a$prefix, "_group_summary.csv")), row.names = FALSE)
write.csv(data.frame(exposure = grid, predicted = pr), file.path(a$outdir, paste0(a$prefix, "_predictions.csv")), row.names = FALSE)

if (toupper(a$plot) == "TRUE") {
  png(file.path(a$outdir, paste0(a$prefix, ".png")), width = 840, height = 540, res = 110)
  plot(d$E, d$Y, col = as.integer(factor(d$G)) + 1,
       pch = 16, xlab = a$exposure, ylab = if (a$type == "binary") "P(response)" else "Response",
       main = sprintf("ER: %s (AIC %.1f)", sel, aics[[sel]]))
  lines(grid, pr, lwd = 2)
  if (a$type == "binary") points(summ$mean_exposure, summ$mean_response, pch = 4, cex = 1.6, lwd = 2)
  legend("topleft", legend = unique(d$G), col = seq_along(unique(d$G)) + 1, pch = 16, bty = "n", title = "group")
  invisible(dev.off())
}
cat(sprintf("n=%d type=%s selected=%s seed=%d rate_mode=%s\n", nrow(d), a$type, sel, a$seed,
            if (nzchar(a$response)) "observed" else a$`rate-mode`))
print(tab, row.names = FALSE)
print(summ, row.names = FALSE)
