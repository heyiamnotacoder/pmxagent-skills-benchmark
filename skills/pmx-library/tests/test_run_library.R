library(testthat)

script <- normalizePath(file.path("..", "scripts", "run_library.R"))

lib <- function(...) {
  out <- suppressWarnings(system2("Rscript", c(script, ...), stdout = TRUE, stderr = TRUE))
  if (!is.null(attr(out, "status"))) stop(paste(out, collapse = "\n"))
  out
}
simdir <- function(...) { dir <- tempfile("lib"); lib("simulate", "--outdir", dir, ...); dir }

test_that("list and search the pinned catalogue", {
  out <- lib("list")
  expect_match(out[1], "^614 of 614 models")
  s <- lib("list", "--search", "pembrolizumab")
  expect_true(any(grepl("Ahamadi_2017_pembrolizumab", s)))
})

test_that("show prints reference, covariates and parameters; unknown model errors", {
  s <- lib("show", "--model", "PK_2cmt_mAb_Davda_2014")
  expect_true(any(grepl("reference: Davda JP", s))); expect_true(any(grepl("covariates required: WT", s)))
  expect_error(lib("show", "--model", "not_a_model"), "unknown model")
})

test_that("typical-value 1-CM oral simulation matches Bateman with model's own parameters", {
  suppressPackageStartupMessages({ library(nlmixr2lib); library(rxode2) })
  ini <- suppressMessages(rxode2::rxode2(readModelDb("PK_1cmt")))$iniDf
  th <- setNames(ini$est, ini$name)
  ka <- exp(th[["lka"]]); cl <- exp(th[["lcl"]]); vc <- exp(th[["lvc"]]); k <- cl / vc
  t <- c(0, 0.5, 1, 2, 6, 12, 24)
  d <- read.csv(file.path(simdir("--model", "PK_1cmt", "--dose", "100", "--times", paste(t, collapse = ","), "--no-iiv"), "library_sim.csv"))
  expect_equal(d$IPRED, 100 * ka / (vc * (ka - k)) * (exp(-k * t) - exp(-ka * t)), tolerance = 1e-4)
})

test_that("IIV simulation is seed-reproducible and needs covariates", {
  a <- read.csv(file.path(simdir("--model", "PK_2cmt_mAb_Davda_2014", "--dose", "100", "--end", "28", "--covariates", "WT=70", "--n", "20"), "library_sim.csv"))
  b <- read.csv(file.path(simdir("--model", "PK_2cmt_mAb_Davda_2014", "--dose", "100", "--end", "28", "--covariates", "WT=70", "--n", "20"), "library_sim.csv"))
  expect_identical(a, b); expect_equal(length(unique(a$ID)), 20)
  expect_error(lib("simulate", "--model", "PK_2cmt_mAb_Davda_2014", "--dose", "100", "--end", "28", "--outdir", tempdir()),
               "model needs covariates: WT")
})
