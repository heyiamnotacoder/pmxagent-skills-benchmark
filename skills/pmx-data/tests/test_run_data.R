library(testthat)

script <- normalizePath(file.path("..", "scripts", "run_data.R"))
nca <- normalizePath(file.path("..", "..", "pmx-nca", "scripts", "run_nca.R"))

std <- function(path, ...) {
  dir <- tempfile("dat"); dir.create(dir)
  out <- system2("Rscript", c(script, "--input", path, "--outdir", dir, ...), stdout = TRUE, stderr = TRUE)
  if (!is.null(attr(out, "status"))) stop(paste(out, collapse = "\n"))
  list(d = read.csv(file.path(dir, "adpc.csv"), na.strings = "."), qc = readLines(file.path(dir, "adpc_qc.txt")),
       f = file.path(dir, "adpc.csv"), dir = dir)
}
tmpcsv <- function(df, ...) { f <- tempfile(fileext = ".csv"); write.csv(df, f, row.names = FALSE, ...); f }

test_that("long file with BLQ strings, dose and route columns", {
  f <- tmpcsv(data.frame(Subject = c(1, 1, 1, 1), Time = c(0, 1, 2, 4), Conc = c("<LLOQ", "10.5", "5", "BLQ"),
                         Dose = 100, Route = "PO", Unit = "ng/mL"))
  r <- std(f, "--subject", "Subject", "--time", "Time", "--conc", "Conc", "--unit-col", "Unit")
  o <- r$d[r$d$EVID == 0, ]
  expect_equal(o$AVAL, c(0, 10.5, 5, 0)); expect_equal(o$BLQ, c(1, 0, 0, 1))
  expect_equal(unique(o$ROUTE), 2); expect_equal(unique(r$d$DOSE), 100)
  expect_equal(sum(r$d$EVID == 1), 1); expect_equal(unique(o$AVALU), "ng/mL")
})

test_that("wide file: times parsed from column names", {
  f <- tmpcsv(data.frame(ID = 1:2, DRUG = "A", DOSE = c(10, 20), ROUTE = "IV",
                         `C_0h` = c(5, 10), `C_1h` = c(4, 8), `C_2h` = c(3, 6), `C_8h` = c("BQL", "0.5"), check.names = FALSE))
  r <- std(f)
  expect_true(any(grepl("format: wide", r$qc)))
  o <- r$d[r$d$EVID == 0 & r$d$USUBJID == 2, ]
  expect_equal(o$ATPTN, c(0, 1, 2, 8)); expect_equal(o$AVAL, c(10, 8, 6, 0.5))
  expect_equal(r$d$BLQ[r$d$EVID == 0 & r$d$USUBJID == 1 & r$d$ATPTN == 8], 1)
  expect_equal(unique(r$d$ROUTE), 1)
})

test_that("NONMEM file: EVID/AMT/DV, route inferred from CMT", {
  f <- tmpcsv(data.frame(ID = c(1, 1, 1, 2, 2, 2), TIME = c(0, 1, 2, 0, 1, 2), AMT = c(50, 0, 0, 80, 0, 0),
                         DV = c(0, 3, 2, 0, 4, 1), EVID = c(1, 0, 0, 1, 0, 0), MDV = c(1, 0, 0, 1, 0, 0), CMT = c(1, 2, 2, 2, 2, 2)))
  r <- std(f)
  expect_true(any(grepl("format: nonmem", r$qc)))
  expect_equal(unique(r$d$DOSE[r$d$USUBJID == 1]), 50); expect_equal(unique(r$d$ROUTE[r$d$USUBJID == 1]), 2)
  expect_equal(unique(r$d$ROUTE[r$d$USUBJID == 2]), 1)
})

test_that("unit conversion only when asked; molar units refused with warning", {
  f <- tmpcsv(data.frame(ID = c(1, 1, 2, 2), TIME = c(1, 2, 1, 2), CONC = c(1000, 500, 2, 1), DOSE = 1, ROUTE = 1,
                         AVALU = c("ng/mL", "ng/mL", "nmol/L", "nmol/L")))
  r0 <- std(f); expect_equal(r0$d$AVAL[r0$d$EVID == 0 & r0$d$USUBJID == 1], c(1000, 500))
  r <- std(f, "--to-unit", "ug/mL")
  expect_equal(r$d$AVAL[r$d$EVID == 0 & r$d$USUBJID == 1], c(1, 0.5))
  expect_equal(r$d$AVAL[r$d$EVID == 0 & r$d$USUBJID == 2], c(2, 1))
  expect_true(any(grepl("cannot convert unit 'nmol/L'", r$qc)))
})

test_that("Excel input", {
  skip_if_not_installed("writexl")
  f <- tempfile(fileext = ".xlsx")
  writexl::write_xlsx(data.frame(ID = 1, TIME = c(0, 1, 2), CONC = c(0, 5, 2), DOSE = 10, ROUTE = 2), f)
  r <- std(f); expect_equal(r$d$AVAL[r$d$EVID == 0], c(0, 5, 2))
})

test_that("round trip: messy wide file -> pmx-data -> pmx-nca equals NCA of the clean long file", {
  t <- c(0, 0.5, 1, 2, 4, 8, 12, 24)
  clean <- do.call(rbind, lapply(1:3, function(i) {
    cc <- round(20 * i * (exp(-0.2 * t) - exp(-1.5 * t)), 4); cc[8] <- 0
    rbind(data.frame(USUBJID = i, DRUG = "X", EVID = 1, ATPTN = 0, AVAL = NA, DOSE = 100 * i, ROUTE = 2, BLQ = NA),
          data.frame(USUBJID = i, DRUG = "X", EVID = 0, ATPTN = t, AVAL = cc, DOSE = 100 * i, ROUTE = 2, BLQ = c(1, rep(0, 6), 1)))
  }))
  clean$AVAL[clean$EVID == 0 & clean$ATPTN == 0] <- 0
  fc <- tmpcsv(clean, na = ".")
  obs <- clean[clean$EVID == 0, ]
  w <- reshape(obs[, c("USUBJID", "ATPTN", "AVAL")], idvar = "USUBJID", timevar = "ATPTN", direction = "wide")
  names(w) <- sub("AVAL\\.", "T", names(w)); w$T0 <- "<LLOQ"; w$T24 <- "BLQ"
  w$DRUG <- "X"; w$DOSE <- 100 * w$USUBJID; w$ROUTE <- "oral"; names(w)[1] <- "Patient"
  r <- std(tmpcsv(w), "--subject", "Patient", "--time-cols", "^T[0-9.]+$")
  run <- function(f) { dir <- tempfile(); system2("Rscript", c(nca, "--input", f, "--outdir", dir,
                        if (grepl("adpc", f)) c("--group", "GROUP") ), stdout = FALSE, stderr = FALSE)
                       read.csv(file.path(dir, "nca_results_individual.csv")) }
  a <- run(fc); b <- run(r$f)
  expect_equal(b$PPSTRESN, a$PPSTRESN, tolerance = 1e-10)
  expect_equal(b$PPTESTCD, a$PPTESTCD)
})
