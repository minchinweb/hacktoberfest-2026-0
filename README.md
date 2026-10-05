# receipt2bean

Photograph a receipt, get a [Beancount](https://beancount.github.io/)
transaction.

Built for the Hacktoberfest 2026 Weekend Challenge ("Build for a Friend") for
my business partner, who photographs receipts but doesn't want to learn
plain-text accounting. A local open-weight vision model reads each photo. Plain
Python then checks the arithmetic and writes the entry. **Nothing leaves your
machine.**

**State**: Proof of concept; works with provided sample datea. Much more
customization is likely needed, and I'd like to eventually have a decent test
suite too.

```
receipt photo --> open-weight vision model (Ollama) --> JSON
              --> Python: validate totals + GST, map accounts
              --> staging.bean  (pending "!" entries, reviewed before they join the ledger)
```

## Design choices

- **The model reads, code checks.** The model returns JSON constrained to a
  schema. Then Python verifies `subtotal + GST = total`, that line items add
  up, that GST is plausible (about 5%), and that the date is sane. Failures are
  flagged with `; REVIEW:` comments. Numbers are never silently "fixed".
- **Entries are always pending (`!`).** Nothing touches the real ledger until a
  human has looked at it.
- **The entry always balances.** Expense = total - GST, GST goes to its own
  account.
- **Idempotent.** Each photo's hash is stored as `receipt-sha` metadata, so
  re-running over the same folder skips receipts already staged.
- **Categories come from your rules, not the model.** `rules.toml` maps
  merchant names to accounts. Unknown merchants land in
  `Expenses:Uncategorized` and get flagged.

## Setup

1. Install [Ollama](https://ollama.com) and pull a vision model:

   ```
   ollama pull qwen3-vl:8b      # check the Ollama library for current tags/sizes
   ```

   Pick a size your RAM/GPU can run. Any Ollama vision model works via
   `--model`.
2. Python 3.11+:

   ```
   pip install -r requirements.txt
   ```

3. Copy `rules.example.toml` to `rules.toml` and set your account names.

## Use

```
# one receipt, print the entry only
python receipt2bean.py receipt.jpg --config rules.toml --dry-run

# a whole folder, append to the staging file
python receipt2bean.py ~/receipts/ --config rules.toml --out staging.bean
```

Then, in your main ledger:

```
include "staging.bean"
```

Review the `!` entries (in Fava or a text editor), fix anything marked `; REVIEW:`, change
`!` to `*` when happy.

PDFs (e.g. emailed online-order receipts) work too: page 1 is rendered with poppler's
`pdftoppm` (`apt install poppler-utils`).

### Sample receipts

`samples/receipts/` holds three **fictional** receipts, and `samples/expected/` holds the
correct answer for each, so you can measure accuracy honestly:

| File | What it tests |
|---|---|
| `01_maple_print_order.jpg` | clean print-shop order, many line items |
| `02_prairie_hardware_photo.jpg` | till receipt, rotated "phone photo" |
| `03_corner_cafe_tip_photo.jpg` | has a tip, so subtotal + GST != total and the entry should get a `; REVIEW:` flag |

Regenerate with `python samples/make_sample_receipts.py`.

Real-world quirk: some stores round GST per line, so printed GST can differ from
5% of the subtotal by a cent or two. The checker tolerates 2 cents.

### Testing without a model

`samples/` has saved extractions. This exercises the validation and output code with no
model running:

```
python receipt2bean.py samples/ --from-json --config rules.example.toml --dry-run
```

## Output example

```
2026-10-02 ! "Staples" "Printer paper and pens"
  receipt: "IMG_2041.jpg"
  receipt-sha: "67f51433225d"
  scanned-by: "qwen3-vl:8b"
  Expenses:Office                                42.00 CAD
  Assets:GST-Receivable                           2.10 CAD
  Liabilities:Visa                              -44.10 CAD
```

## Limitations (honest list)

- Single expense posting per receipt (no per-line splitting yet).
- GST only (Alberta). HST/PST provinces would need more tax fields.
- Refunds / negative totals are not handled.
- HEIC photos aren't supported; set the phone camera to JPEG ("most
  compatible").
- PDFs: first page only. HEIC photos aren't supported; set the phone camera to JPEG ("most compatible").
- Accuracy depends on the model and photo quality. See the write-up for numbers from
  real receipts.
- Multi-currency and bank-statement matching are not implemented.

## Ideas next

- Phone-synced "inbox" folder so receipts get scanned automatically
- Match staged entries to bank-import transactions to avoid double entry
- Hook into a GST plugin using `g`/`z`/`e` line markers (i.e. auto-managed GST
  calculations, confirmed to match the receipt)
- Split by line item into categories

## License

MIT
