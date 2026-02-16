# Tasks: Prepare for Open Source Publishing

**Input**: Design documents from `/specs/001-prepare-for-oss/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: This feature is focused on setting up the development environment and CI/CD pipeline, so the tests are primarily about ensuring the commands and workflows function correctly.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Path Conventions

- Paths shown below assume repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create `requirements` directory
- [X] T002 [P] Create `requirements/base.in` with production dependencies
- [X] T003 [P] Create `requirements/dev.in` with development dependencies
- [X] T004 Generate `requirements/base.txt` and `requirements/dev.txt` using `pip-compile`
- [X] T005 Update `.gitignore` to ignore `__pycache__`, `.pytest_cache`, and other temporary files

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- [X] T006 Update `docker-compose.yml` to include a service for LocalStack
- [X] T007 Create `.github/workflows/ci.yml` with jobs for linting, formatting, and testing

---

## Phase 3: User Story 1 - Local Development Setup (Priority: P1) 🎯 MVP

**Goal**: A new contributor can set up a local development environment quickly and easily.

**Independent Test**: Run `make local-dev` and verify that all services are running and the application is accessible.

### Implementation for User Story 1

- [X] T008 [US1] Implement `make local-dev` target in `Makefile` to start Docker containers
- [X] T009 [US1] Implement `make stop` target in `Makefile` to stop Docker containers

---

## Phase 4: User Story 2 - Automated Testing (Priority: P2)

**Goal**: A developer can run the entire test suite with a single command.

**Independent Test**: Run `make test` and verify that all tests pass.

### Implementation for User Story 2

- [ ] T010 [US2] Implement `make test` target in `Makefile` to run the `pytest` test suite
- [ ] T011 [US2] Ensure all existing tests pass when run with `make test`

---

## Phase 5: User Story 3 - Continuous Integration (Priority: P3)

**Goal**: A CI/CD pipeline automatically runs the test suite on every push and pull request.

**Independent Test**: Push a commit to a branch and verify that the GitHub Actions workflow is triggered and completes successfully.

### Implementation for User Story 3

- [ ] T012 [US3] Implement the `test` job in `.github/workflows/ci.yml` to run the test suite using `moto`

---

## Phase 6: User Story 4 - Open Source Documentation (Priority: P4)

**Goal**: Clear and comprehensive documentation is available for contributors.

**Independent Test**: Review the generated documentation to ensure it is clear and accurate.

### Implementation for User Story 4

- [ ] T013 [P] [US4] Create `CONTRIBUTING.md` with instructions for setting up the development environment, running tests, and submitting pull requests
- [ ] T014 [P] [US4] Review and update `README.md` for clarity and accuracy
- [ ] T015 [P] [US4] Ensure a `LICENSE` file exists in the repository root

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T016 Implement `make lint` target in `Makefile` to run `flake8`
- [ ] T017 Implement `make format` target in `Makefile` to run `black`
- [ ] T018 Run `make format` to format the entire codebase
- [ ] T019 Run `make lint` and fix any linting errors
- [ ] T020 [P] Validate the instructions in `quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- All user stories are independent of each other and can be worked on in parallel after the Foundational phase is complete.

---

## Implementation Strategy

### Incremental Delivery

1.  Complete Setup + Foundational → Foundation ready
2.  Add User Story 1 → Test independently
3.  Add User Story 2 → Test independently
4.  Add User Story 3 → Test independently
5.  Add User Story 4 → Test independently
6.  Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
