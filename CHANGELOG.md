# Changelog

## [0.2.0](https://github.com/goatlabshq/goatnotify/compare/v0.1.0...v0.2.0) (2026-10-23)


### Features

* **core:** render mailable subjects from subject_template() ([d582e75](https://github.com/goatlabshq/goatnotify/commit/d582e758e052891f2455e2736963e91e2b0b2ce4))
* **django:** re-export the common helpers from goatnotify.django ([c42f360](https://github.com/goatlabshq/goatnotify/commit/c42f3603f833fbfd0a09a30168b94ca6bba6993d))
* **django:** warn when enqueue() would send inline through ImmediateBackend ([947fe4f](https://github.com/goatlabshq/goatnotify/commit/947fe4f8d88207d6a6440f536ffa6f7575f80898))


### Bug Fixes

* **ci:** claim every pending PyPI project before uploading ([c083f60](https://github.com/goatlabshq/goatnotify/commit/c083f604ccf043dc2b8a7dbb8432758d35b2b39e))
* **ci:** publish without attestations from the reusable release workflow ([4e7ae34](https://github.com/goatlabshq/goatnotify/commit/4e7ae3478cfcebb5844d8b7fa6ec22465b47921a))
* **deps:** upgrade certifi to 2026.10.19 for PYSEC-2026-4320 ([2b155f2](https://github.com/goatlabshq/goatnotify/commit/2b155f242dd50340fe20ebd15d68ed859e4d080c))
* **django:** resolve the lazy re-exports without a dynamic import ([ecf2420](https://github.com/goatlabshq/goatnotify/commit/ecf24209452cfaeb1ea9271b9f27141969da6314))


### Documentation

* drop blocktranslate from the Django subject template example ([5d56919](https://github.com/goatlabshq/goatnotify/commit/5d56919dbe28af73df30c406038720d3ce618cbf))

## 0.1.0 (2026-10-19)


### Features

* bound how long draining the queue can take ([99163d0](https://github.com/goatlabshq/goatnotify/commit/99163d012259015ad806e6c0e08c319adee528d8))
* **core:** add mailables, the mailer and the email channel ([569bc6a](https://github.com/goatlabshq/goatnotify/commit/569bc6a6d4862d9a4ead7620cc9be19a5dcfb174))
* **core:** add notifications, channels, results and events ([0f8c078](https://github.com/goatlabshq/goatnotify/commit/0f8c078ecdc4c88a3612da2bcd05940e6d372959))
* **core:** add the database channel and notification store protocol ([9d66db1](https://github.com/goatlabshq/goatnotify/commit/9d66db1a14e824ea70d2b7ff8ffbf96fe7a88666))
* **core:** add the error hierarchy and retry policies ([9eaa4b4](https://github.com/goatlabshq/goatnotify/commit/9eaa4b47b7a626e168cbe8a19d04e7d4ff4e7c91))
* **core:** add the HTTP transport and the webhook channel ([f1fb8a4](https://github.com/goatlabshq/goatnotify/commit/f1fb8a438e5f73dbfed7b857ff851ca8e2b3a0b2))
* **core:** add the notifier with retries, hooks and results ([4ab2598](https://github.com/goatlabshq/goatnotify/commit/4ab2598f28f760fc5ba7f5bd5124a8ea7b429287))
* **core:** add the queue protocol and the asyncio reference queue ([fdd767b](https://github.com/goatlabshq/goatnotify/commit/fdd767ba57bc09cc9ec07d41df9ad1f097c01dec))
* **core:** add the rendered email model and MIME conversion ([b37dc02](https://github.com/goatlabshq/goatnotify/commit/b37dc0226609144f78bf942d26607802546dc054))
* **core:** add the SMTP transport ([03f1386](https://github.com/goatlabshq/goatnotify/commit/03f138688a5905a658324357d022c937272f9980))
* **core:** cap every retry delay with RetryPolicy.max_delay ([0ac5a7b](https://github.com/goatlabshq/goatnotify/commit/0ac5a7bcb9108814cf2c24fecfcd0ba1520d354e))
* **core:** identify outgoing HTTP requests as goatnotify ([01e36ab](https://github.com/goatlabshq/goatnotify/commit/01e36ab2b5c1ba9340c696b3febdff64008c0545))
* **core:** let notifications name the recipient parameter freely ([7eafd73](https://github.com/goatlabshq/goatnotify/commit/7eafd73c5fa2465e33556a2c9be1b90acf76d257))
* **django:** add the Django Tasks queue and the settings-driven notifier ([94a47a4](https://github.com/goatlabshq/goatnotify/commit/94a47a44d211176575100c9cbb3689029d001af4))
* **django:** add the email transport, template renderer and ORM store ([f961ac0](https://github.com/goatlabshq/goatnotify/commit/f961ac0421c82b54d7b4ea22370789c1cfc7aaee))
* **django:** report invalid settings through Django system checks ([2a656c1](https://github.com/goatlabshq/goatnotify/commit/2a656c1d517bf23848e4b03e9a75c78f66e0d301))
* expose the public API from goatnotify and goatnotify.core ([d142b19](https://github.com/goatlabshq/goatnotify/commit/d142b190f0b1e4f0e200946fab458c662587369c))
* **fastapi:** add the lifespan and notifier dependency ([d877e75](https://github.com/goatlabshq/goatnotify/commit/d877e758c3e27047d014acc125596f0be7858ee0))
* **jinja:** add the Jinja2 template renderer ([6179858](https://github.com/goatlabshq/goatnotify/commit/6179858f20126a34b5955e46aa2dc3711260d14e))
* make queued deliveries idempotent across task retries ([f15a0ed](https://github.com/goatlabshq/goatnotify/commit/f15a0eda11d003470728671c79c61bca1bb2e2cb))


### Bug Fixes

* **core:** accept exactly one mailbox per address ([cf92a94](https://github.com/goatlabshq/goatnotify/commit/cf92a94295d6cba5de7df8824efc881ae9cb440e))
* **core:** ignore non-ASCII digits in Retry-After ([3106d3e](https://github.com/goatlabshq/goatnotify/commit/3106d3e47ca0144dc202c7be572f3c20e9b6e858))
* **core:** keep webhook URLs out of every transport error ([90d89a8](https://github.com/goatlabshq/goatnotify/commit/90d89a831a77aa4e698a23521c00da3121055261))
* **core:** nest all inline images in one related part with valid content ids ([9dd9d52](https://github.com/goatlabshq/goatnotify/commit/9dd9d5242d37a426455d37ae7c9af2326556bc0b))
* **core:** return HTTP redirects instead of following them ([5735b16](https://github.com/goatlabshq/goatnotify/commit/5735b16c46b704a2e1d7601d54337dd05987fe50))
* **core:** stop AsyncioQueue.drain from spinning on finished tasks ([903e48a](https://github.com/goatlabshq/goatnotify/commit/903e48a98da66d9baa54429fe7d666eddbeac399))
* **core:** treat SMTP certificate errors as permanent ([2d61784](https://github.com/goatlabshq/goatnotify/commit/2d6178410ce9f57591e7ee232b4a156ad945c155))
* **core:** validate header names and reserve every envelope header ([20ac9d1](https://github.com/goatlabshq/goatnotify/commit/20ac9d1d7bab84d35b39935e2460f5e727883697))
* **django:** add sync helpers that do not deadlock in ASGI sync views ([69c4610](https://github.com/goatlabshq/goatnotify/commit/69c4610b02146605465d1a6f2b86c971a049ae8e))
* **django:** declare the asgiref dependency it imports ([35bd72d](https://github.com/goatlabshq/goatnotify/commit/35bd72dcdd779bc6e430d205a98e6c27da996971))
* **django:** honour a custom Message-ID whatever its case ([1d73ab5](https://github.com/goatlabshq/goatnotify/commit/1d73ab59d45e751453119541cfc11289c51cfd8f))
* **django:** queue only exact JSON values and import only installed apps ([39b74cc](https://github.com/goatlabshq/goatnotify/commit/39b74cce10c458ebb317f11b83f3ce83c181c7fa))
* **django:** send email off the thread-sensitive executor ([cbcddf4](https://github.com/goatlabshq/goatnotify/commit/cbcddf408602957714744056e79afa3d2efaa7b7))
* **django:** send inline images with their content id ([41d7a51](https://github.com/goatlabshq/goatnotify/commit/41d7a510be3bc92832f689cfd662bb822209b759))
* **django:** skip queued notifications whose recipient was deleted ([87680b5](https://github.com/goatlabshq/goatnotify/commit/87680b5ba6bc13726d0e27668fe6e6468fd3be8a))
* **jinja:** load templates off the event loop ([6217a86](https://github.com/goatlabshq/goatnotify/commit/6217a869075659f86a5cea281ebf09986e1a7859))
* keep the asyncio queue usable across event loops and app restarts ([b01ea00](https://github.com/goatlabshq/goatnotify/commit/b01ea00fa51432be7535d72ba9dcfb2669e31a51))


### Documentation

* add goatnotify design spec ([d313632](https://github.com/goatlabshq/goatnotify/commit/d31363214f15b86dd431670d289db05891a185b6))
* add the goatnotify implementation plan ([75db53c](https://github.com/goatlabshq/goatnotify/commit/75db53c51d73b31dfc0e00c9085172eb6d394d7f))
* add the README, the documentation site and the project guide ([09d3c93](https://github.com/goatlabshq/goatnotify/commit/09d3c93d14e252ef85304c5d8139c47ebf1e4635))
* align the goatnotify spec with the implementation plan ([8041436](https://github.com/goatlabshq/goatnotify/commit/80414362bc6f1f06ead799f10ac4682af142ce3c))
* align the spec with Django 6.1 and the security tooling ([1699af6](https://github.com/goatlabshq/goatnotify/commit/1699af6b87e0c3263fee8d93c48c6130a7b739c7))
* align the spec with the implementation and document on_commit ([e951d55](https://github.com/goatlabshq/goatnotify/commit/e951d55871495ca3f7cf0ca5f132435806d5d17e))
* generate llms.txt and llms-full.txt with mkdocs-llmstxt ([f565db7](https://github.com/goatlabshq/goatnotify/commit/f565db79858b4e17a0989cc3d97b82b548e2a3c1))
* stop excluding the gitignored superpowers directory ([9d101f1](https://github.com/goatlabshq/goatnotify/commit/9d101f1ef76994828ed5c1c0147a20bf24f65cf4))
