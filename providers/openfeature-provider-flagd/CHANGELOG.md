# Changelog

## [0.1.5](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.1.4...openfeature-provider-flagd/v0.1.5) (2024-04-11)


### ✨ New Features

* in-process offline flagd resolver ([#74](https://github.com/open-feature/python-sdk-contrib/issues/74)) ([8cea506](https://github.com/open-feature/python-sdk-contrib/commit/8cea5066ee96f637f3108a9dc3a7539c450a14be))

## [0.1.4](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.1.3...openfeature-provider-flagd/v0.1.4) (2024-03-26)


### 🐛 Bug Fixes

* include targetingKey in flagd serialized evaluation context ([#58](https://github.com/open-feature/python-sdk-contrib/issues/58)) ([ddd79a4](https://github.com/open-feature/python-sdk-contrib/commit/ddd79a49b765aa0679a2c1938447c61b37b6d0fe))
* respect timeout setting in grpc method calls ([#60](https://github.com/open-feature/python-sdk-contrib/issues/60)) ([0149cf7](https://github.com/open-feature/python-sdk-contrib/commit/0149cf7ced8116f54a9b220549834a1970460bd9))
* return proper metadata object in FlagdProvider ([#59](https://github.com/open-feature/python-sdk-contrib/issues/59)) ([6508234](https://github.com/open-feature/python-sdk-contrib/commit/6508234486ba0b650e849cbee22505988233131a))


### ✨ New Features

* implement environment-variable based config ([#62](https://github.com/open-feature/python-sdk-contrib/issues/62)) ([a8b78b2](https://github.com/open-feature/python-sdk-contrib/commit/a8b78b28fe44ca712b00db04ac1a23a9c9bc6d9b))
* replace schema with tls argument in FlagdProvider constructor ([#61](https://github.com/open-feature/python-sdk-contrib/issues/61)) ([7a7210f](https://github.com/open-feature/python-sdk-contrib/commit/7a7210f6f63a9cba886f4d512c01ebac39d910a9))


### 🧹 Chore

* exclude generated protobuf files from coverage report ([#51](https://github.com/open-feature/python-sdk-contrib/issues/51)) ([660a0cb](https://github.com/open-feature/python-sdk-contrib/commit/660a0cbc9bb932ac0dd9cb09f1d75177b161601b))


### 🔄 Refactoring

* add mypy and fix typing issues ([#72](https://github.com/open-feature/python-sdk-contrib/issues/72)) ([b405925](https://github.com/open-feature/python-sdk-contrib/commit/b4059255045cdb7054a35bc338207e23c42ce068))

## [0.1.3](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.1.2...openfeature-provider-flagd/v0.1.3) (2024-02-23)


### 🐛 Bug Fixes

* include proto file in build for openfeature-provider-flagd ([#45](https://github.com/open-feature/python-sdk-contrib/issues/45)) ([7783cc8](https://github.com/open-feature/python-sdk-contrib/commit/7783cc8e7fb8fe0f9b812938efcd1f4c07e3ff68))

## [0.1.2](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd-v0.1.1...openfeature-provider-flagd/v0.1.2) (2024-02-22)


### 🐛 Bug Fixes

* remove mention of local eval in readme ([41df80e](https://github.com/open-feature/python-sdk-contrib/commit/41df80e1b3044356e3b228a484f3a13c92068d91))
* remove setup from flagd tests ([#39](https://github.com/open-feature/python-sdk-contrib/issues/39)) ([85661ff](https://github.com/open-feature/python-sdk-contrib/commit/85661ff170b378d37b0a3d5d0a955dad3417f538))


### 🧹 Chore

* **main:** release providers/flagd 0.1.1 ([#40](https://github.com/open-feature/python-sdk-contrib/issues/40)) ([d42ee1e](https://github.com/open-feature/python-sdk-contrib/commit/d42ee1e531249e0023456dbe46db2f4f0c52a5c5))

## [0.1.1](https://github.com/open-feature/python-sdk-contrib/compare/providers/flagd-v0.1.0...providers/flagd/v0.1.1) (2024-02-22)


### 🐛 Bug Fixes

* remove setup from flagd tests ([#39](https://github.com/open-feature/python-sdk-contrib/issues/39)) ([85661ff](https://github.com/open-feature/python-sdk-contrib/commit/85661ff170b378d37b0a3d5d0a955dad3417f538))
