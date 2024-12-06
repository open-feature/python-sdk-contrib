# Changelog

## [0.2.0](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.1.5...openfeature-provider-flagd/v0.2.0) (2024-12-06)


### ⚠ BREAKING CHANGES

* **flagd-rpc:** add events for rpc mode, some breaking config fixes ([#108](https://github.com/open-feature/python-sdk-contrib/issues/108))

### 🐛 Bug Fixes

* **flagd:** fix semver version parsing to allow "v" prefix([#106](https://github.com/open-feature/python-sdk-contrib/issues/106)) ([#107](https://github.com/open-feature/python-sdk-contrib/issues/107)) ([93fee85](https://github.com/open-feature/python-sdk-contrib/commit/93fee8593c8c278dff6371b68b21366bea9d5f01))
* **flagd:** improve targeting and fix fractional issue([#92](https://github.com/open-feature/python-sdk-contrib/issues/92)) ([#105](https://github.com/open-feature/python-sdk-contrib/issues/105)) ([eb31b83](https://github.com/open-feature/python-sdk-contrib/commit/eb31b8324662df113cd27205eb12f09a1cf30b06))
* object resolution for RPC and Object types, add test-harness ([ca76802](https://github.com/open-feature/python-sdk-contrib/commit/ca7680242085fb9b77d9b0844147468544010074))
* object resolution for RPC and Object types, add test-harness. ([#103](https://github.com/open-feature/python-sdk-contrib/issues/103)) ([ca76802](https://github.com/open-feature/python-sdk-contrib/commit/ca7680242085fb9b77d9b0844147468544010074))
* remove modifications to license files ([#81](https://github.com/open-feature/python-sdk-contrib/issues/81)) ([a23f61e](https://github.com/open-feature/python-sdk-contrib/commit/a23f61e1c14c70e45a4bce4a014d5599813f1d28))


### ✨ New Features

* Change fractional custom op from percentage-based to relative weighting. ([#91](https://github.com/open-feature/python-sdk-contrib/issues/91)) ([7b34822](https://github.com/open-feature/python-sdk-contrib/commit/7b34822afdabfb89e991ae81a91681cafcbdfbd3))
* **flagd-rpc:** add caching  ([#110](https://github.com/open-feature/python-sdk-contrib/issues/110)) ([16179e3](https://github.com/open-feature/python-sdk-contrib/commit/16179e3e68eb5bc18b5d12ec80caf511b7dec762))
* **flagd-rpc:** add events for rpc mode, some breaking config fixes ([#108](https://github.com/open-feature/python-sdk-contrib/issues/108)) ([b62d3d1](https://github.com/open-feature/python-sdk-contrib/commit/b62d3d1ab5ce40f275e795ae2682ae3fe315f431))


### 🔄 Refactoring

* replace typing_extensions import ([#98](https://github.com/open-feature/python-sdk-contrib/issues/98)) ([adb8a69](https://github.com/open-feature/python-sdk-contrib/commit/adb8a69d9ed1b0b03cb96d924b2269d973822794))

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
