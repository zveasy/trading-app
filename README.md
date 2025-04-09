# trading-app
# Setup Instructions

1. Clone the repo
2. Make the script executable:

   chmod +x gridlock_scaffold.sh

3. Run it:

   ./gridlock_scaffold.sh

# GRIDLOCK Logs

This folder contains structured development logs using the **GRIDLOCK System** — a 14-day rinse-and-repeat cycle designed to help developers ship features with clarity, momentum, and resilience against unknowns.

Each feature or module lives in its own timestamped folder (e.g., `2025-04-09_user-referral-system`) and includes:

- `gutcheck.md`: Day 1 feature breakdown and risk assessment
- Optional files:
  - `sprint_a_plan.md`
  - `lessons_learned.md`
  - `demo_day_notes.md`
  - `test_results.md`

---

## GRIDLOCK 14-Day Cycle Overview

| Phase                 | Days        | Purpose                             |
|-----------------------|-------------|-------------------------------------|
| **Gut Check**         | Day 1       | Define problem, risks, expectations |
| **Sprint Planning**   | Day 2       | Task breakdown & ownership          |
| **Sprint A**          | Days 3–7    | Core build + mid-sprint demo        |
| **Sprint B**          | Days 8–12   | Edge cases, testing, polish         |
| **Ship Window**       | Day 13      | Deploy or merge final build         |
| **Retro & Reset**     | Day 14      | Reflect, document, reset cycle      |

---

## How to Scaffold a New Feature Log

Run the setup script to scaffold a new GRIDLOCK folder.

### 1. Make the script executable (first time only)

```bash
chmod +x gridlock_scaffold.sh