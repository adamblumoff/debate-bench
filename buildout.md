1. Goals

Debate Bench should:

Run structured debates between pairs of models on a given motion.

Score each debate on several dimensions, for example:

Persuasion

Reasoning

Factuality

Clarity

Safety

Use a panel of 3 LLM judges for each debate:

Each judge gives per dimension scores and a winner label (Pro, Con, Tie).

The panel is sampled at random from a configurable judge pool.

Aggregate results:

Panel majority decides the debate winner.

Average per dimension scores across judges.

Compute Elo style ratings for each model based on win, loss, draw.

Store all debates, judge outputs, and ratings to disk in simple file formats.

Support dynamic reruns over time, while keeping benchmark versions reproducible.

2. CLI Overview

Implement a command line tool named debatebench with at least these commands:

debatebench init

Create default config files and results folders.

debatebench run (or run-tournament)

Run a batch of debates between models on a set of topics.

Log debate transcripts, judge outputs, and aggregated results.

debatebench rate (or recompute-ratings)

Recompute Elo ratings from stored debate results.

debatebench show-leaderboard (or leaderboard)

Display the current model leaderboard using the latest ratings file.

Optional later:

debatebench inspect-debate to print a single debate and its judge decisions.

3. Project Layout

Create a Python package with this structure:

Top level package directory, for example debatebench/

cli.py for CLI entrypoints

config.py for loading and validating config files

models.py for model adapter logic (both debaters and judges)

debate.py for orchestrating debates

judge.py for running judge panels and aggregating scores

rating.py for Elo rating logic

storage.py for file read and write

schema.py for data structures or type definitions

Also include:

configs/ folder

Main benchmark configuration file

Topic list file

Debater models file

Judge models file

results/ folder

Debate results file (one debate per line)

Ratings file (current Elo ratings per model)

4. Configuration Files

Codex should implement config loading and validation for the following files.

4.1 Main benchmark config

Contents:

Benchmark and rubric versions

Debate format:

List of rounds, each with:

speaker: Pro or Con

stage: opening, rebuttal, closing, etc

Token limit per turn

Language (e.g. English)

Scoring:

List of dimensions:

persuasion

reasoning

factuality

clarity

safety

Numeric scale (for example 0 to 10)

Number of judges per debate (3)

Elo:

Initial rating (for example 1500)

K factor (for example 20 to 32)

4.2 Topics list

Contents:

List of topics

For each topic:

Unique id

Motion text

Optional category label

4.3 Debater models

Contents:

List of debater model entries

For each:

Name or id

Provider type (for example OpenAI, generic HTTP, local)

Model identifier or endpoint url

Token limits or other relevant parameters

4.4 Judge models

Contents:

List of judge model entries

For each:

Name or id

Provider type

Model identifier or endpoint

Optional judge prompt style key, used to pick the correct template

Note: judge pool must not include the same models that are being evaluated as debaters.

5. Data Schema Requirements

Codex should define internal data structures and file formats for:

5.1 Debate transcript

Contains:

Debate id

Benchmark format and rubric versions

Topic info:

id

motion

category

Pro model id

Con model id

List of turns:

Turn index

Speaker (Pro or Con)

Stage (opening, rebuttal, closing, etc)

Text content

Metadata:

Timestamp

Random seed used for any sampling

5.2 Single judge result

For each judge in the panel:

Judge id

Scores per side per dimension:

For Pro:

persuasion

reasoning

factuality

clarity

safety

For Con:

same set of dimensions

Winner label:

“pro”, “con”, or “tie”

5.3 Stored debate result

Each stored debate result record should contain:

Full debate transcript object

List of judge result objects

Aggregated result:

Panel winner:

Majority vote over judge winners, or tie if no majority

Mean scores per dimension per side across judges:

For Pro

For Con

All debate results should be stored in one file as one record per line, using a consistent schema.

5.4 Ratings file

Ratings file should contain:

Benchmark and rubric versions

Elo settings used (initial rating, K factor)

A mapping of model id to:

Current rating

Number of debates played

6. Core Modules and Responsibilities

Codex should implement modules with these responsibilities.

6.1 Config loading module

Responsibilities:

Load all config files from disk

Validate structure and required fields

Provide typed accessors for:

Main benchmark config

Topics list

Debater models

Judge models

6.2 Model adapter module

Responsibilities:

Provide a common interface to call any underlying model

Support at least:

OpenAI style models

Generic HTTP chat completion endpoints

Separate types for:

Debater models

Judge models

Hide provider specific details from the rest of the system

6.3 Debate orchestration module

Responsibilities:

Given:

A topic

A Pro model

A Con model

Global config

Random seed

Produce a complete debate transcript

For each round:

Identify speaker (Pro or Con)

Build appropriate prompts for that speaker:

Motion text

Role (Pro or Con)

Stage (opening, rebuttal, closing)

Full history of previous turns

Call the correct model adapter

Append its reply as a new turn

Return the transcript object

6.4 Judge panel module

Responsibilities:

Given a debate transcript and scoring settings:

Randomly sample 3 judge models from the judge pool, using a seed

For each judge:

Build a judge prompt that:

Explains roles and motion

Includes the full transcript

Explains scoring dimensions and numeric scale

Requests a structured JSON style output with:

Per side scores per dimension

Winner label

Call the judge model and parse its output into a judge result object

Retry or handle errors where output is malformed

Aggregate the panel:

Compute panel winner by majority vote over judge winner labels

Compute mean scores per side per dimension

Return:

List of raw judge results

Aggregated result object

6.5 Elo rating module

Responsibilities:

Implement expected score calculation for two ratings

Implement Elo update rule for a single game:

Input ratings for A and B

Input result for A (1 win, 0.5 draw, 0 loss)

Output new ratings for A and B

Implement a function to recompute all ratings from a list of stored debates:

Initialize each model with initial rating from config

Sort debates in a deterministic order (for example by timestamp or id)

For each debate:

Extract Pro model id, Con model id, and aggregate winner

Map winner to results for Pro and Con:

Pro win: Pro 1, Con 0

Con win: Pro 0, Con 1

Tie: both 0.5

Update both models’ ratings

Increment games played counters

Return final rating and games played per model

6.6 Storage module

Responsibilities:

Append a single stored debate record to the debates file

Read all debate records from the debates file

Read and write ratings file

Handle basic error cases like missing files

6.7 CLI module

Responsibilities:

Implement CLI commands and map them to the above modules

Parse arguments and forward them to appropriate functions

Handle errors gracefully and print clear messages

7. CLI Command Behavior

Codex should implement the following behaviors.

7.1 debatebench init

Tasks:

Create configs directory if missing

Create default:

Main benchmark config

Topics file (with a small example list)

Models file

Judges file

Create results directory if missing

Do not overwrite existing config files without an explicit flag

7.2 debatebench run or debatebench run-tournament

Inputs (parameters):

Paths to:

Main config

Topics file

Models file

Judges file

Number of topics to sample, or a flag to use all topics

Number of debates per model pair per topic

Random seed for reproducibility

Behavior:

Load configs and construct debater and judge model objects.

Choose topics:

Either the full set or a random subset.

Generate a schedule of debates:

Distinct model pairs (A, B) where A is not B.

For each pair and topic:

Optionally randomize which side is Pro and which is Con.

For each scheduled debate:

Run a debate using the debate module.

Judge the debate using the judge panel module.

Compose a stored debate record:

Transcript

Judge results

Aggregated result

Append the record to the debates results file.

7.3 debatebench rate or recompute-ratings

Inputs:

Path to debates results file

Path to main config

Path to ratings output file (optional, default location allowed)

Behavior:

Load debates and main config.

Infer the set of debater models from either config or from the debate records.

Recompute ratings from scratch using the Elo module.

Write the resulting ratings file.

7.4 debatebench show-leaderboard or leaderboard

Inputs:

Path to ratings file

Optional top N parameter to limit display

Behavior:

Load ratings file.

Sort models by rating in descending order.

Print a table with:

Rank

Model id

Rating

Number of debates played

Optionally later:

Also show average scores per dimension by model, computed from debate records.

7.5 (Optional) debatebench inspect-debate

Inputs:

Debate id

Path to debates file

Behavior:

Load debates file.

Find the debate with that id.

Print:

Topic and model names

Full transcript in order

Raw judge results

Aggregated winner and scores

8. Implementation Phases

Suggested implementation order for Codex:

Project skeleton

Create package and module files

Add stub CLI commands that just print that they were called

Config loading

Implement parsing and validation for all config files

Provide strongly typed accessors

Model adapters

Implement minimal adapters for at least one provider

Allow configuration driven creation of debater and judge model objects

Debate engine

Implement debate orchestration for a single debate

Verify transcript structure and basic flow

Judge engine

Implement judging for a single judge

Add 3 judge panel logic and aggregation

Storage

Implement read and write of stored debate records

Confirm that debates are appended correctly

Elo ratings

Implement rating recomputation from a small set of synthetic debates

Confirm rating changes behave as expected

Wiring into CLI

Connect run command to debate and judge modules and storage

Connect rate command to rating and storage

Connect show-leaderboard command to ratings file

Hardening

Add basic error handling and logging

Add simple seed control for reproducibility

At that point Debate Bench should be able to:

Run structured debates between any configured models

Judge them with a 3 model panel

Keep per debate dimension scores

Maintain Elo ratings and show a leaderboard

ChatGPT can make mistakes. Check important info.