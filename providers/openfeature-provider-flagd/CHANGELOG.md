# Changelog

## [0.2.6](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.2.5...openfeature-provider-flagd/v0.2.6) (2025-07-22)


### 🐛 Bug Fixes

* **flagd:** Add upperbound to protobuf version to reduce potential conflict with other version ([5ad2896](https://github.com/open-feature/python-sdk-contrib/commit/5ad289683a0d9128a53d142d2804f9fffb9dd36f))
* **flagd:** adjust flagd to updated error codes ([#285](https://github.com/open-feature/python-sdk-contrib/issues/285)) ([64d755b](https://github.com/open-feature/python-sdk-contrib/commit/64d755b869a076216a91b2d409b1ba5d627ebe08))
* **flagd:** fix protobuf version for file generation to lowest 5.x version ([#280](https://github.com/open-feature/python-sdk-contrib/issues/280)) ([5ad2896](https://github.com/open-feature/python-sdk-contrib/commit/5ad289683a0d9128a53d142d2804f9fffb9dd36f))

## [0.2.5](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.2.4...openfeature-provider-flagd/v0.2.5) (2025-07-08)


### 🐛 Bug Fixes

* **flagd:** reduce loglevel of expected logs ([#277](https://github.com/open-feature/python-sdk-contrib/issues/277)) ([cca865f](https://github.com/open-feature/python-sdk-contrib/commit/cca865f490cc699ecf038c934dfccacad9bda8d2))

## [0.2.4](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.2.3...openfeature-provider-flagd/v0.2.4) (2025-06-10)


### 🐛 Bug Fixes

* add retry policy to grpc calls. ([#261](https://github.com/open-feature/python-sdk-contrib/issues/261)) ([07ee909](https://github.com/open-feature/python-sdk-contrib/commit/07ee90925126817b6e17387182656a2a0f5603e3))


### 🧹 Chore

* **deps:** update dependency grpcio-health-checking to v1.72.1 ([#258](https://github.com/open-feature/python-sdk-contrib/issues/258)) ([e087353](https://github.com/open-feature/python-sdk-contrib/commit/e0873538bf34ec773fb5dc8af60b422c111492e9))
* **deps:** update dependency grpcio-health-checking to v1.73.0 ([#259](https://github.com/open-feature/python-sdk-contrib/issues/259)) ([7a080b0](https://github.com/open-feature/python-sdk-contrib/commit/7a080b077dc50d3b2512a967bb845fee5af05460))
* **deps:** update dependency providers/openfeature-provider-flagd/openfeature/test-harness to v2.7.4 ([#237](https://github.com/open-feature/python-sdk-contrib/issues/237)) ([65f70d2](https://github.com/open-feature/python-sdk-contrib/commit/65f70d2dde6e5bdbfd110ac4ec4e4f9cb4793c9c))
* **deps:** update dependency providers/openfeature-provider-flagd/openfeature/test-harness to v2.8.0 ([#239](https://github.com/open-feature/python-sdk-contrib/issues/239)) ([709ed25](https://github.com/open-feature/python-sdk-contrib/commit/709ed25dfa23ae85aebb5b1dfed1f7ba06b60e39))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to 18cde17 ([#233](https://github.com/open-feature/python-sdk-contrib/issues/233)) ([bf9ef82](https://github.com/open-feature/python-sdk-contrib/commit/bf9ef82b73c8b14784c9a3bc1e27681d8445005d))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to 36944c6 ([#240](https://github.com/open-feature/python-sdk-contrib/issues/240)) ([030c6ed](https://github.com/open-feature/python-sdk-contrib/commit/030c6edfd9439e3e8c61492936c450ca9a5a062e))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to bb2dc2c ([#256](https://github.com/open-feature/python-sdk-contrib/issues/256)) ([34979b6](https://github.com/open-feature/python-sdk-contrib/commit/34979b61793a3e60e36da9e010ff606ede392b63))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to cbfa0a9 ([#260](https://github.com/open-feature/python-sdk-contrib/issues/260)) ([d0ec36f](https://github.com/open-feature/python-sdk-contrib/commit/d0ec36feb113f5ad11c49c49821527e70be2afd0))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to d27e000 ([#242](https://github.com/open-feature/python-sdk-contrib/issues/242)) ([fd97b35](https://github.com/open-feature/python-sdk-contrib/commit/fd97b35ca91ffdcf7a7a2d6962ca0e1b87b66dd3))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to edf0deb ([#248](https://github.com/open-feature/python-sdk-contrib/issues/248)) ([1771423](https://github.com/open-feature/python-sdk-contrib/commit/1771423afa23c4fa6b430c5d22686fa7c36fb1e8))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to f014806 ([#253](https://github.com/open-feature/python-sdk-contrib/issues/253)) ([067f19f](https://github.com/open-feature/python-sdk-contrib/commit/067f19f5e56e48c8d2866691397b2082c396936f))

## [0.2.3](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.2.2...openfeature-provider-flagd/v0.2.3) (2025-04-11)


### 🐛 Bug Fixes

* **flagd:** fix parameter name inconsistency with SDK version 0.8.1 ([#232](https://github.com/open-feature/python-sdk-contrib/issues/232)) ([55ee420](https://github.com/open-feature/python-sdk-contrib/commit/55ee42087bd9a948a130b08671395138baa33621))


### ✨ New Features

* add support for flagd flag metadata ([#215](https://github.com/open-feature/python-sdk-contrib/issues/215)) ([6dc72c0](https://github.com/open-feature/python-sdk-contrib/commit/6dc72c0e16b01cd40e6c103884a2d457e95871d1))


### 🧹 Chore

* **deps:** update dependency providers/openfeature-provider-flagd/openfeature/test-harness to v2.7.3 ([#226](https://github.com/open-feature/python-sdk-contrib/issues/226)) ([9a0971c](https://github.com/open-feature/python-sdk-contrib/commit/9a0971c1fd67998259903a3ea4b42772413fc259))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to 130df3e ([#222](https://github.com/open-feature/python-sdk-contrib/issues/222)) ([fa7f429](https://github.com/open-feature/python-sdk-contrib/commit/fa7f4293e060a3d56b204db851c19a668076e7a7))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to 27e4461 ([#223](https://github.com/open-feature/python-sdk-contrib/issues/223)) ([9bf2e42](https://github.com/open-feature/python-sdk-contrib/commit/9bf2e421e52922516afa2e5b8648b52a035a038d))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to aad6193 ([#194](https://github.com/open-feature/python-sdk-contrib/issues/194)) ([277ad0e](https://github.com/open-feature/python-sdk-contrib/commit/277ad0e744764bbc4eb5c5ebb773287bc2607ac3))

## [0.2.2](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.2.1...openfeature-provider-flagd/v0.2.2) (2025-03-18)


### 🐛 Bug Fixes

* **flagd:** handle falsy target values correctly ([#214](https://github.com/open-feature/python-sdk-contrib/issues/214)) ([fafd099](https://github.com/open-feature/python-sdk-contrib/commit/fafd099f07365a7d0032e8215477b51bfe90c01a))


### 🧹 Chore

* **deps:** update dependency grpcio-health-checking to v1.71.0 ([#209](https://github.com/open-feature/python-sdk-contrib/issues/209)) ([345e793](https://github.com/open-feature/python-sdk-contrib/commit/345e7934b9de3879d3aff45c8213ece1a98e3711))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.11.0 ([#212](https://github.com/open-feature/python-sdk-contrib/issues/212)) ([1b9b5f1](https://github.com/open-feature/python-sdk-contrib/commit/1b9b5f128a7fe08ffbf84cbc7de2986f95dc01f5))
* **flagd:** Add sync metadata disabled ([#211](https://github.com/open-feature/python-sdk-contrib/issues/211)) ([2f85057](https://github.com/open-feature/python-sdk-contrib/commit/2f850574943cc92d55d198c8ccd91e80583a2ee6))

## [0.2.1](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.2.0...openfeature-provider-flagd/v0.2.1) (2025-03-10)


### ✨ New Features

* **flagd:** Add features to customize auth to Sync API servers ([#203](https://github.com/open-feature/python-sdk-contrib/issues/203)) ([5151e94](https://github.com/open-feature/python-sdk-contrib/commit/5151e941d229101bdbcc5b40f570f69d77ddda7b))
* **flagd:** Context value hydration ([#195](https://github.com/open-feature/python-sdk-contrib/issues/195)) ([4fa619b](https://github.com/open-feature/python-sdk-contrib/commit/4fa619b93faf1d1f62a9ead99f33baa21c04e267))

## [0.2.0](https://github.com/open-feature/python-sdk-contrib/compare/openfeature-provider-flagd/v0.1.5...openfeature-provider-flagd/v0.2.0) (2025-02-18)


### ⚠ BREAKING CHANGES

* drop Python 3.8 support ([#187](https://github.com/open-feature/python-sdk-contrib/issues/187))
* **flagd-rpc:** add events for rpc mode, some breaking config fixes ([#108](https://github.com/open-feature/python-sdk-contrib/issues/108))

### 🐛 Bug Fixes

* **flagd:** fix semver version parsing to allow "v" prefix([#106](https://github.com/open-feature/python-sdk-contrib/issues/106)) ([#107](https://github.com/open-feature/python-sdk-contrib/issues/107)) ([93fee85](https://github.com/open-feature/python-sdk-contrib/commit/93fee8593c8c278dff6371b68b21366bea9d5f01))
* **flagd:** improve targeting and fix fractional issue([#92](https://github.com/open-feature/python-sdk-contrib/issues/92)) ([#105](https://github.com/open-feature/python-sdk-contrib/issues/105)) ([eb31b83](https://github.com/open-feature/python-sdk-contrib/commit/eb31b8324662df113cd27205eb12f09a1cf30b06))
* object resolution for RPC and Object types, add test-harness ([ca76802](https://github.com/open-feature/python-sdk-contrib/commit/ca7680242085fb9b77d9b0844147468544010074))
* object resolution for RPC and Object types, add test-harness. ([#103](https://github.com/open-feature/python-sdk-contrib/issues/103)) ([ca76802](https://github.com/open-feature/python-sdk-contrib/commit/ca7680242085fb9b77d9b0844147468544010074))
* remove modifications to license files ([#81](https://github.com/open-feature/python-sdk-contrib/issues/81)) ([a23f61e](https://github.com/open-feature/python-sdk-contrib/commit/a23f61e1c14c70e45a4bce4a014d5599813f1d28))


### ✨ New Features

* attempts with connection improvements ([#118](https://github.com/open-feature/python-sdk-contrib/issues/118)) ([8e23a70](https://github.com/open-feature/python-sdk-contrib/commit/8e23a700244a85291671b41083b1be82670cf79d))
* Change fractional custom op from percentage-based to relative weighting. ([#91](https://github.com/open-feature/python-sdk-contrib/issues/91)) ([7b34822](https://github.com/open-feature/python-sdk-contrib/commit/7b34822afdabfb89e991ae81a91681cafcbdfbd3))
* **flagd-rpc:** add caching  ([#110](https://github.com/open-feature/python-sdk-contrib/issues/110)) ([16179e3](https://github.com/open-feature/python-sdk-contrib/commit/16179e3e68eb5bc18b5d12ec80caf511b7dec762))
* **flagd-rpc:** add events for rpc mode, some breaking config fixes ([#108](https://github.com/open-feature/python-sdk-contrib/issues/108)) ([b62d3d1](https://github.com/open-feature/python-sdk-contrib/commit/b62d3d1ab5ce40f275e795ae2682ae3fe315f431))
* **flagd-rpc:** adding grace attempts ([#117](https://github.com/open-feature/python-sdk-contrib/issues/117)) ([41d0ad8](https://github.com/open-feature/python-sdk-contrib/commit/41d0ad8b6a5b32272c75684cfcbabffb57e53470))
* **flagd:** add custom cert path ([#131](https://github.com/open-feature/python-sdk-contrib/issues/131)) ([f50351a](https://github.com/open-feature/python-sdk-contrib/commit/f50351a0435064111fb98753a49139fafa8307e6))
* **flagd:** Add in-process evaluator ([#104](https://github.com/open-feature/python-sdk-contrib/issues/104)) ([01285e7](https://github.com/open-feature/python-sdk-contrib/commit/01285e726baa3acbf1b5d6ed0e802be54342a6d9))
* **flagd:** add ssl cert path option ([f50351a](https://github.com/open-feature/python-sdk-contrib/commit/f50351a0435064111fb98753a49139fafa8307e6))
* **flagd:** migrate to new provider mode file and update e2e tests ([#121](https://github.com/open-feature/python-sdk-contrib/issues/121)) ([eed1ee0](https://github.com/open-feature/python-sdk-contrib/commit/eed1ee053191ecaca21f82749da9fe443712206f))
* **flagd:** use test-harness version number for integration tests ([#120](https://github.com/open-feature/python-sdk-contrib/issues/120)) ([3c3e9c8](https://github.com/open-feature/python-sdk-contrib/commit/3c3e9c86e7111fc165eebd650453069a0e8f4dae))


### 🧹 Chore

* **deps:** update dependency grpcio-health-checking to v1.68.1 ([#125](https://github.com/open-feature/python-sdk-contrib/issues/125)) ([4e75a36](https://github.com/open-feature/python-sdk-contrib/commit/4e75a366468ab0f588031587a7224d16ae6cd0c6))
* **deps:** update dependency grpcio-health-checking to v1.69.0 ([#147](https://github.com/open-feature/python-sdk-contrib/issues/147)) ([905b42b](https://github.com/open-feature/python-sdk-contrib/commit/905b42b6e654c86c9161f02d87a812ad4ac42bed))
* **deps:** update dependency grpcio-health-checking to v1.70.0 ([#168](https://github.com/open-feature/python-sdk-contrib/issues/168)) ([06a9b58](https://github.com/open-feature/python-sdk-contrib/commit/06a9b5880093680575422e3e16d14a81f2cd7bef))
* **deps:** update dependency providers/openfeature-provider-flagd/openfeature/test-harness to v0.5.21 ([#145](https://github.com/open-feature/python-sdk-contrib/issues/145)) ([1495263](https://github.com/open-feature/python-sdk-contrib/commit/149526337c5fd9948e10a1e3aab0176f2d1e7c8b))
* **deps:** update dependency providers/openfeature-provider-flagd/openfeature/test-harness to v2 ([#178](https://github.com/open-feature/python-sdk-contrib/issues/178)) ([ce16a54](https://github.com/open-feature/python-sdk-contrib/commit/ce16a5406e7e2d36fabe1ebe704f3a528e72027f))
* **deps:** update dependency providers/openfeature-provider-flagd/openfeature/test-harness to v2.2.0 ([#190](https://github.com/open-feature/python-sdk-contrib/issues/190)) ([9db9ad6](https://github.com/open-feature/python-sdk-contrib/commit/9db9ad62445deae3bb50505cb9d6a902d3234d34))
* **deps:** update pre-commit hook astral-sh/ruff-pre-commit to v0.9.0 ([#149](https://github.com/open-feature/python-sdk-contrib/issues/149)) ([24b11e1](https://github.com/open-feature/python-sdk-contrib/commit/24b11e14599251a47d70ee5b4080a326206f85a6))
* **deps:** update providers/openfeature-provider-flagd/openfeature/schemas digest to 76d611f ([#138](https://github.com/open-feature/python-sdk-contrib/issues/138)) ([853ece7](https://github.com/open-feature/python-sdk-contrib/commit/853ece72feb558b208cad5680c358c4b09aabf91))
* **deps:** update providers/openfeature-provider-flagd/openfeature/schemas digest to b81a56e ([#134](https://github.com/open-feature/python-sdk-contrib/issues/134)) ([a2a0ba0](https://github.com/open-feature/python-sdk-contrib/commit/a2a0ba0d9a59c763829fa630fdc2f28b93b2f037))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to 54952f3 ([#188](https://github.com/open-feature/python-sdk-contrib/issues/188)) ([d88b29a](https://github.com/open-feature/python-sdk-contrib/commit/d88b29a01b14d411027007395e6de881602e91a1))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to 5b07065 ([#171](https://github.com/open-feature/python-sdk-contrib/issues/171)) ([6f45c15](https://github.com/open-feature/python-sdk-contrib/commit/6f45c15b4da2a404cc0583fa3c4f8d22de13fad1))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to 6c673d7 ([#151](https://github.com/open-feature/python-sdk-contrib/issues/151)) ([1c2c650](https://github.com/open-feature/python-sdk-contrib/commit/1c2c650bd7f0f5b5953bbb3948c3d657172e46ff))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to 8d6eeb3 ([#177](https://github.com/open-feature/python-sdk-contrib/issues/177)) ([02dcfc0](https://github.com/open-feature/python-sdk-contrib/commit/02dcfc02089f3a0a3f300e3a2485e9f847ff765e))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to 95fe981 ([#184](https://github.com/open-feature/python-sdk-contrib/issues/184)) ([f1fb247](https://github.com/open-feature/python-sdk-contrib/commit/f1fb2477f61a1a37ecfcbd858a80bdfac277340b))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to a69f748 ([#193](https://github.com/open-feature/python-sdk-contrib/issues/193)) ([4251f36](https://github.com/open-feature/python-sdk-contrib/commit/4251f36d8ac1fbb70e44a87bea3b2755bcf09ecf))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to be56f22 ([#186](https://github.com/open-feature/python-sdk-contrib/issues/186)) ([a15d5a2](https://github.com/open-feature/python-sdk-contrib/commit/a15d5a230e5a7d5a66a2cce4341f312bf98a3503))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to d261f68 ([#140](https://github.com/open-feature/python-sdk-contrib/issues/140)) ([6801522](https://github.com/open-feature/python-sdk-contrib/commit/68015220ea9005286c0a45d4cdeb3891d9f43b3b))
* **deps:** update providers/openfeature-provider-flagd/openfeature/spec digest to ed0f9ef ([#135](https://github.com/open-feature/python-sdk-contrib/issues/135)) ([bee9205](https://github.com/open-feature/python-sdk-contrib/commit/bee9205d475473b5005fbbea9b4b5c756ad1d20e))
* drop Python 3.8 support ([#187](https://github.com/open-feature/python-sdk-contrib/issues/187)) ([b55cc1e](https://github.com/open-feature/python-sdk-contrib/commit/b55cc1e0f823d05a330c12af6861dbd3bec69c3a))


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
