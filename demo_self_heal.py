"""Explicitly seeded logic-bug demo using Synthetix's normal repair pipeline."""
import argparse
import json

from counter_check import check_counter
from synthetix import run_pipeline


PROMPT = (
    "Build a dark-themed counter starting at zero. Keep the heading and the "
    "visible counter. Include buttons named Increase, Decrease, and Reset. "
    "Increase must add exactly one, Decrease must subtract exactly one, "
    "and Reset must return the number to zero. Use purple accents."
)

BROKEN_COUNTER = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Synthetix controlled repair demo</title>
  <style>
    body { margin:0; min-height:100vh; display:grid; place-items:center;
           background:#101014; color:#f5f3ff; font-family:system-ui,sans-serif; }
    main { text-align:center; padding:2rem; }
    output { display:block; font-size:4rem; margin:1.5rem; color:#c4b5fd; }
    button { margin:.3rem; padding:.8rem 1.2rem; border:0; border-radius:.6rem;
             background:#7c3aed; color:white; cursor:pointer; font:inherit; }
    button:focus-visible { outline:3px solid white; outline-offset:3px; }
    .label { color:#c4b5fd; }
  </style>
</head>
<body>
  <main>
    <p class="label">Controlled demo — deliberately seeded logic bug</p>
    <h1>Synthetix Counter</h1>
    <output id="count" aria-live="polite">0</output>
    <button id="increase">Increase</button>
    <button id="decrease">Decrease</button>
    <button id="reset">Reset</button>
  </main>
  <script>
    let count = 0;
    const display = document.getElementById('count');
    function render() { display.textContent = String(count); }
    document.getElementById('increase').addEventListener('click', () => {
      count += 2; // Intentional demo bug: the requirement says add one.
      render();
    });
    document.getElementById('decrease').addEventListener('click', () => {
      count -= 1;
      render();
    });
    document.getElementById('reset').addEventListener('click', () => {
      count = 0;
      render();
    });
  </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--check-only', action='store_true',
        help='Detect the seeded bug without making any model requests.',
    )
    args = parser.parse_args()

    if args.check_only:
        print('CONTROLLED DEMO: checking the intentionally broken counter.')
        report = check_counter(BROKEN_COUNTER)
        print(json.dumps(report, indent=2))
        if report['javascript_errors'] or report['console_errors']:
            print('Unexpected runtime errors: the intended fixture is a logic-only failure.')
            return 1
        if not report['behavior_errors']:
            print('FAIL: The checker did not detect the intentional bug.')
            return 1
        if report['behavior_errors'][0]['step'] != 'Increase changes 0 to 1':
            print('FAIL: The fixture failed before the intended Increase check.')
            return 1
        print('\nPASS: The checker detected the deliberate Increase bug.')
        print('No model requests were made.')
        return 0

    result = run_pipeline(
        PROMPT,
        use_counter_checks=True,
        initial_html=BROKEN_COUNTER,
        demo_label='Increase adds two instead of one',
    )
    return 0 if result.get('counter_behavior_verified') else 1


if __name__ == '__main__':
    raise SystemExit(main())
