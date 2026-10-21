---
name: technical-due-diligence
description: Versions, benchmarks on matched hardware, maintenance status, licence and known vulnerabilities.
when: choosing a library, database, framework, model, protocol or hosting provider
---

# Technical due diligence

## Facts that decide, in order

1. **Does it do the job?** The specific capability the user needs, documented,
   not implied by the marketing page.
2. **Is it maintained?** Last release date, commit cadence over the last twelve
   months, open critical issues, whether a security advisory was answered.
3. **What does it cost at the user's scale?** Licence, per-seat or per-request
   pricing, egress, the tier where the free plan stops.
4. **What breaks?** Known limits: row counts, timeouts, payload sizes, quotas,
   regional availability, breaking-change history.
5. **Who else uses it, at what scale?** A named production user beats any
   benchmark.

## Benchmarks

A benchmark is only evidence with the hardware, the version, the dataset and
the date attached. Vendor benchmarks are marketing until reproduced. If two
benchmarks disagree, report both and the reason they might — usually a different
workload shape, not a different truth.

Never average benchmark numbers. Never compare a p50 from one with a p99 from
another.

## Licence and security

State the licence by name (MIT, Apache-2.0, AGPL-3.0, BUSL…) and what it means
for the user's use — commercial, closed-source, SaaS, redistribution. Check the
advisory database for the specific version. "No known vulnerabilities" is a
claim with a date.

## Maturity language

Do not describe a project as "mature" or "production-ready". Give the number
that made you think so: years since 1.0, number of releases, whether the last
release was a patch, count of maintainers, whether there is a paid support tier.
