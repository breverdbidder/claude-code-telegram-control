# Expense Analyzer Skill

## Description
Scan PDF receipts in a designated folder and generate a categorized expense breakdown.

## Instructions
1. Look for the expenses folder at ~/Documents/Expenses or ~/Desktop/Expenses
2. Read all PDF files in the folder
3. Extract: date, vendor, amount, payment method from each receipt
4. Categorize into: Business, Food, Travel, Software/Subscriptions, Office, Other
5. Generate a summary with:
   - Total spend
   - Spend by category (with percentages)
   - Top 5 largest expenses
   - Monthly trend if multiple months present
6. Save report as expenses-report.html on desktop

## Output Format
Clean HTML report with:
- Summary stats at top
- Category breakdown table
- Itemized receipt list sorted by amount (descending)
- Flagged items: any over $500, any duplicates

## Trigger
Run when I say: "expenses", "receipt scan", "expense report", or "what did I spend"
