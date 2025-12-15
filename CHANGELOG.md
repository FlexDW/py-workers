# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-12-15

### Fixed
- Fixed critical deadlock bug when using both `size` and `rate` limits together

### Changed
- Replaced `self.count` integer with `_executing` list for clearer state management
- Simplified shutdown logic to properly await all task futures

## [0.1.0] - Initial Release

### Added
- WorkerPool with size-based concurrency limiting
- WorkerPool with rate-based execution limiting
- Task retry logic with configurable backoff strategies
- Async context manager interface
