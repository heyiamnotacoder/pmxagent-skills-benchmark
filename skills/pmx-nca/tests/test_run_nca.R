library(testthat)

script <- normalizePath(file.path(dirname(sys.frame(1)$ofile %||% "."), "..", "scripts", "run_nca.R"), mustWork = FALSE)
if (!file.exists(script)) script <- normalizePath(file.path("..", "scripts", "run_nca.R"))
`%||%` <- function(x, y) if (is.null(x)) y else x

run <- function(df, ...) {
  dir <- tempfile("nca"); dir.create(dir)
  inp <- file.path(dir, "in.csv"); write.csv(df, inp, row.names = FALSE, na = ".")
  out <- system2("Rscript", c(script, "--input", inp, "--outdir", dir, ...), stdout = TRUE, stderr = TRUE)
  st <- attr(out, "status") %||% 0
  if (st != 0) stop(paste(out, collapse = "\n"))
  list(ind = read.csv(file.path(dir, "nca_results_individual.csv"), stringsAsFactors = FALSE),
       mean = read.csv(file.path(dir, "nca_results_mean.csv"), stringsAsFactors = FALSE), dir = dir)
}
val <- function(r, code, subj = 1) with(r$ind, PPSTRESN[PPTESTCD == code & USUBJID == subj])

make <- function(times, conc, dose = 100, route = 1, subj = 1, drug = "X", blq = NULL) {
  obs <- data.frame(USUBJID = subj, DRUG = drug, EVID = 0, ATPTN = times, AVAL = conc, DOSE = dose, ROUTE = route,
                    BLQ = if (is.null(blq)) 0 else blq)
  rbind(data.frame(USUBJID = subj, DRUG = drug, EVID = 1, ATPTN = 0, AVAL = NA, DOSE = dose, ROUTE = route, BLQ = NA), obs)
}

test_that("IV bolus mono-exponential matches analytical AUCinf, HL, CL, Vz", {
  C0 <- 10; k <- 0.1; D <- 100; t <- c(0, 1, 2, 4, 8, 12, 24)
  r <- run(make(t, C0 * exp(-k * t), dose = D, route = 1))
  auc_inf <- C0 / k
  expect_equal(val(r, "HL_Lambda_z"), log(2) / k, tolerance = 1e-6)
  expect_equal(val(r, "AUCINF_obs"), auc_inf, tolerance = 1e-6)   # log-down is exact for exponential decay
  expect_equal(val(r, "CL_obs"), D / auc_inf, tolerance = 1e-6)
  expect_equal(val(r, "Vz_obs"), D / auc_inf / k, tolerance = 1e-6)
  expect_equal(val(r, "Cmax"), C0); expect_equal(val(r, "Tmax"), 0)
  expect_equal(val(r, "Rsq_adjusted"), 1, tolerance = 1e-9)
  expect_equal(nrow(r$ind[r$ind$PPTESTCD %in% c("CLF_obs", "VzF_obs"), ]), 0)
})

test_that("extravascular: lin-up/log-down AUClast by hand, CL/F and Vz/F labels", {
  t <- c(0, 0.5, 1, 2, 4, 8, 12, 24); ka <- 1.2; k <- 0.15
  cc <- 50 * (exp(-k * t) - exp(-ka * t))
  r <- run(make(t, cc, route = 2))
  man <- 0
  for (i in 2:length(t)) {
    dt <- t[i] - t[i - 1]; c1 <- cc[i - 1]; c2 <- cc[i]
    man <- man + if (c2 >= c1 || c2 <= 0) dt * (c1 + c2) / 2 else dt * (c1 - c2) / log(c1 / c2)
  }
  expect_equal(val(r, "AUClast"), man, tolerance = 1e-8)
  expect_equal(val(r, "Cmax"), max(cc)); expect_equal(val(r, "Tmax"), t[which.max(cc)])
  expect_true(length(val(r, "CLF_obs")) == 1 && length(val(r, "VzF_obs")) == 1)
  expect_equal(length(val(r, "CL_obs")), 0)
  # terminal phase is ~pure elimination at late times
  expect_equal(val(r, "HL_Lambda_z"), log(2) / k, tolerance = 1e-2)
})

test_that("linear trapezoid option differs from lin-up/log-down only on the declining limb", {
  t <- c(0, 1, 2, 4, 8); cc <- c(0, 8, 10, 5, 2.5)
  lin <- run(make(t, cc, route = 2), "--auc-method", "linear")
  expect_equal(val(lin, "AUClast"), sum(diff(t) * (head(cc, -1) + tail(cc, -1)) / 2))
  lud <- run(make(t, cc, route = 2))
  expect_lt(val(lud, "AUClast"), val(lin, "AUClast"))
})

test_that("BLQ default: zero before Tmax, dropped after Tmax", {
  t <- c(0, 0.5, 1, 2, 4, 8, 12, 24); cc <- c(0, 0, 5, 8, 4, 2, 1, 0); blq <- c(1, 1, 0, 0, 0, 0, 0, 1)
  r <- run(make(t, cc, route = 2, blq = blq))
  # AUClast ends at t=12 (trailing BLQ dropped), not at 24
  keep <- 1:7
  man <- 0
  for (i in 2:7) { c1 <- cc[i - 1]; c2 <- cc[i]; dt <- t[i] - t[i - 1]
    man <- man + if (c2 >= c1 || c2 <= 0) dt * (c1 + c2) / 2 else dt * (c1 - c2) / log(c1 / c2) }
  expect_equal(val(r, "AUClast"), man, tolerance = 1e-8)
  # AUClast is defined to Tlast (last measurable), so trailing zeros never add area
  rz <- run(make(t, cc, route = 2, blq = blq), "--blq-rule", "zero")
  expect_equal(val(rz, "AUClast"), val(r, "AUClast"))
  # a BLQ in the middle of the post-Tmax limb: default drops it, "zero" dips to 0 and loses area
  cc2 <- c(0, 0, 5, 8, 0, 2, 1, 0.5); blq2 <- c(1, 1, 0, 0, 1, 0, 0, 0)
  d2 <- run(make(t, cc2, route = 2, blq = blq2)); z2 <- run(make(t, cc2, route = 2, blq = blq2), "--blq-rule", "zero")
  expect_lt(val(z2, "AUClast"), val(d2, "AUClast"))
  expect_equal(val(d2, "AUClast"), 0.5 * 5 / 2 + 1 * (5 + 8) / 2 + 6 * (8 - 2) / log(8 / 2) +
                 4 * (2 - 1) / log(2) + 12 * (1 - 0.5) / log(2), tolerance = 1e-8)
})

test_that("IV without C0 sample back-extrapolates log-linearly", {
  C0 <- 20; k <- 0.2; t <- c(0.5, 1, 2, 4, 8, 12)
  r <- run(make(t, C0 * exp(-k * t), route = 1))
  expect_equal(val(r, "AUCINF_obs"), C0 / k, tolerance = 1e-6)
  expect_equal(val(r, "Cmax"), C0, tolerance = 1e-8)
})

test_that("multiple groups/subjects, combined id style, means, determinism", {
  t <- c(0, 1, 2, 4, 8, 12)
  df <- rbind(make(t, 10 * exp(-0.1 * t), subj = 1, drug = "A"), make(t, 20 * exp(-0.1 * t), subj = 2, drug = "A"),
              make(t, 5 * exp(-0.3 * t), subj = 1, drug = "B"))
  r1 <- run(df, "--id-style", "combined"); r2 <- run(df, "--id-style", "combined")
  expect_setequal(unique(r1$ind$DRUG), c("A_1", "A_2", "B_1"))
  expect_equal(r1$mean$PPSTRESN[r1$mean$DRUG == "A" & r1$mean$PPTESTCD == "Cmax"], 15)
  expect_identical(unname(tools::md5sum(file.path(r1$dir, "nca_results_individual.csv"))),
                   unname(tools::md5sum(file.path(r2$dir, "nca_results_individual.csv"))))
})

test_that("clear error on missing columns", {
  df <- make(c(0, 1, 2), c(1, 2, 1)); df$AVAL <- NULL
  expect_error(suppressWarnings(run(df)), "missing columns")
})
