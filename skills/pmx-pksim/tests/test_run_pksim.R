library(testthat)

script <- normalizePath(file.path("..", "scripts", "run_pksim.R"))

sim <- function(...) {
  dir <- tempfile("sim"); dir.create(dir)
  out <- system2("Rscript", c(script, "--outdir", dir, "--plot", "FALSE", ...), stdout = TRUE, stderr = TRUE)
  if (!is.null(attr(out, "status"))) stop(paste(out, collapse = "\n"))
  list(d = read.csv(file.path(dir, "pk_simulation.csv")), ip = read.csv(file.path(dir, "pk_simulation_individual_params.csv")),
       dir = dir)
}
at <- function(d, id, t) d$CONC[d$USUBJID == id & abs(d$TIME - t) < 1e-9]

test_that("1-CM IV bolus matches D/V*exp(-k t)", {
  r <- sim("--model", "1cmt", "--params", "CL=2,V1=20", "--doses", "100", "--n-per-group", "1", "--end", "24", "--times", "0,1,4,12,24")
  expect_equal(r$d$CONC, 100 / 20 * exp(-0.1 * c(0, 1, 4, 12, 24)), tolerance = 1e-6)
})

test_that("2-CM IV bolus matches the analytical bi-exponential", {
  CL <- 1; V1 <- 10; Q <- 2; V2 <- 20; D <- 50; t <- c(0, 0.5, 2, 8, 24, 72)
  k10 <- CL / V1; k12 <- Q / V1; k21 <- Q / V2
  s <- k10 + k12 + k21; al <- (s + sqrt(s^2 - 4 * k10 * k21)) / 2; be <- (s - sqrt(s^2 - 4 * k10 * k21)) / 2
  A <- D / V1 * (al - k21) / (al - be); B <- D / V1 * (k21 - be) / (al - be)
  r <- sim("--model", "2cmt", "--params", sprintf("CL=%g,V1=%g,Q=%g,V2=%g", CL, V1, Q, V2), "--doses", D,
           "--n-per-group", "1", "--end", "72", "--times", paste(t, collapse = ","))
  expect_equal(r$d$CONC, A * exp(-al * t) + B * exp(-be * t), tolerance = 1e-5)
})

test_that("1-CM oral matches Bateman with F", {
  ka <- 1; k <- 0.1; V <- 10; F <- 0.5; D <- 100; t <- c(0, 0.5, 1, 2, 6, 24)
  r <- sim("--model", "1cmt", "--route", "oral", "--params", sprintf("CL=%g,V1=%g,KA=%g,F=%g", k * V, V, ka, F),
           "--doses", D, "--n-per-group", "1", "--end", "24", "--times", paste(t, collapse = ","))
  expect_equal(r$d$CONC, F * D * ka / (V * (ka - k)) * (exp(-k * t) - exp(-ka * t)), tolerance = 1e-5)
})

test_that("1-CM infusion: concentration at end of infusion", {
  CL <- 2; V <- 20; k <- CL / V; D <- 100; T <- 2
  r <- sim("--model", "1cmt", "--route", "iv-infusion", "--dur", T, "--params", "CL=2,V1=20", "--doses", D,
           "--n-per-group", "1", "--end", "12", "--times", "2,6")
  cend <- D / T / CL * (1 - exp(-k * T))
  expect_equal(r$d$CONC, c(cend, cend * exp(-k * 4)), tolerance = 1e-5)
})

test_that("multiple dosing superposes", {
  r1 <- sim("--model", "1cmt", "--params", "CL=2,V1=20", "--doses", "100", "--n-per-group", "1", "--end", "30",
            "--times", "25", "--ii", "12", "--n-doses", "3")
  expect_equal(r1$d$CONC, 5 * sum(exp(-0.1 * c(25, 13, 1))), tolerance = 1e-6)
})

test_that("BSV: seed reproducible, CV about right, groups and doses laid out", {
  a <- sim("--model", "1cmt", "--params", "CL=2,V1=20", "--doses", "10,30", "--n-per-group", "500", "--end", "24",
           "--bsv", "0.3", "--seed", "7", "--times", "1")
  b <- sim("--model", "1cmt", "--params", "CL=2,V1=20", "--doses", "10,30", "--n-per-group", "500", "--end", "24",
           "--bsv", "0.3", "--seed", "7", "--times", "1")
  expect_identical(a$d, b$d)
  expect_equal(sd(log(a$ip$CL)), sqrt(log(1 + 0.3^2)), tolerance = 0.1)
  expect_equal(as.vector(table(a$d$DOSE)), c(500, 500))
  c7 <- sim("--model", "1cmt", "--params", "CL=2,V1=20", "--doses", "10", "--n-per-group", "5", "--end", "24",
            "--bsv", "0.3", "--seed", "8", "--times", "1")
  expect_false(identical(a$ip$CL[1:5], c7$ip$CL))
})

test_that("per-kg scaling and mAb preset (day -> hour conversion)", {
  r <- sim("--model", "1cmt", "--params", "CL=0.1,V1=0.5", "--per-kg", "--bw", "80", "--doses", "100",
           "--n-per-group", "1", "--end", "1", "--times", "0")
  expect_equal(r$d$CONC, 100 / 40)
  p <- sim("--preset", "mab-davda2014", "--doses", "100", "--n-per-group", "1", "--end", "1", "--times", "0")
  expect_equal(p$ip$CL, 0.2 / 24); expect_equal(p$ip$V1, 3.61); expect_equal(p$d$CONC, 100 / 3.61)
})

test_that("missing parameters give a clear error", {
  expect_error(suppressWarnings(sim("--model", "2cmt", "--params", "CL=1,V1=10", "--doses", "1", "--end", "1")), "missing params")
})
