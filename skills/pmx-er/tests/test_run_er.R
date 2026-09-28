library(testthat)

script <- normalizePath(file.path("..", "scripts", "run_er.R"))

er <- function(df, ...) {
  dir <- tempfile("er"); dir.create(dir)
  inp <- file.path(dir, "in.csv"); write.csv(df, inp, row.names = FALSE)
  out <- system2("Rscript", c(script, "--input", inp, "--outdir", dir, "--plot", "FALSE", ...), stdout = TRUE, stderr = TRUE)
  if (!is.null(attr(out, "status"))) stop(paste(out, collapse = "\n"))
  list(par = read.csv(file.path(dir, paste0("er_parameters.csv"))), data = read.csv(file.path(dir, "er_data.csv")),
       summ = read.csv(file.path(dir, "er_group_summary.csv")))
}
est <- function(r, model, term) r$par$estimate[r$par$model == model & r$par$term == term]

test_that("logistic EC50 = -b0/b1 and matches glm", {
  set.seed(1); E <- runif(400, 0, 100); Y <- rbinom(400, 1, plogis(-3 + 0.06 * E))
  r <- er(data.frame(USUBJID = 1:400, AUClast = E, Y = Y), "--response", "Y", "--models", "logistic")
  g <- coef(glm(Y ~ E, binomial))
  expect_equal(est(r, "logistic", "intercept"), unname(g[1]), tolerance = 1e-8)
  expect_equal(est(r, "logistic", "EC50"), unname(-g[1] / g[2]), tolerance = 1e-8)
})

test_that("exact response-rate generation hits the rates and is seed-reproducible", {
  df <- data.frame(USUBJID = 1:60, DOSEGRP = rep(1:3, each = 20), AUClast = rep(c(100, 300, 1000), each = 20) * runif(60, .8, 1.2))
  a <- er(df, "--group", "DOSEGRP", "--response-rates", "1:0.1,2:0.5,3:0.9")
  b <- er(df, "--group", "DOSEGRP", "--response-rates", "1:0.1,2:0.5,3:0.9")
  expect_equal(a$summ$mean_response, c(0.1, 0.5, 0.9))
  expect_identical(a$data, b$data)
  c <- er(df, "--group", "DOSEGRP", "--response-rates", "1:0.1,2:0.5,3:0.9", "--seed", "3")
  expect_false(identical(a$data$RESPONSE, c$data$RESPONSE))
})

test_that("reads pmx-nca long output directly", {
  long <- data.frame(DOSEGRP = rep(1:2, each = 4), USUBJID = rep(1:4, each = 2),
                     PPTESTCD = rep(c("Cmax", "AUClast"), 4), PPSTRESN = c(1, 10, 2, 20, 3, 30, 4, 40), ROUTE = "iv")
  r <- er(long, "--group", "DOSEGRP", "--response-rates", "1:0.5,2:0.5")
  expect_equal(r$data$AUClast, c(10, 20, 30, 40))
})

test_that("continuous: Emax recovered and selected by AIC over linear", {
  set.seed(2); E <- rep(c(0, 5, 10, 25, 50, 100, 200, 400), each = 10)
  Y <- 2 + 10 * E / (30 + E) + rnorm(length(E), 0, 0.3)
  r <- er(data.frame(USUBJID = seq_along(E), AUClast = E, Y = Y), "--response", "Y", "--type", "continuous",
          "--models", "linear,emax")
  expect_true(all(r$par$selected[r$par$model == "emax"]))
  expect_equal(est(r, "emax", "EC50"), 30, tolerance = 0.15)
  expect_equal(est(r, "emax", "EMAX"), 10, tolerance = 0.05)
})

test_that("continuous: linear data selects linear", {
  set.seed(3); E <- runif(80, 0, 100); Y <- 1 + 0.05 * E + rnorm(80, 0, 0.5)
  r <- er(data.frame(USUBJID = 1:80, AUClast = E, Y = Y), "--response", "Y", "--type", "continuous", "--models", "linear,emax")
  expect_true(all(r$par$selected[r$par$model == "linear"]))
})
