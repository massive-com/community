# When is Amazon's biggest day?

Ten years of European card spending at Amazon, reproduced end-to-end.

Prime Day or Black Friday? Most people pick one. Both answers are right, and both are wrong — it depends what you mean by "biggest," and it depends where you live. This notebook works through the question using about 200,000 rows of daily card-transaction data across the UK, Germany, France, Italy, Spain and a few smaller markets, from 2016 to last week.

The full write-up is on the Massive blog. This repo is the code behind every chart in it.

## What's inside

A single notebook, `amzn_blog_post.ipynb`, that pulls the data from the [Massive API](https://massive.com/docs/rest/alternative/consumer-spending/merchant-aggregates) and builds up the story one figure at a time:

1. **Ten years, one chart.** Daily Amazon retail spend, start of 2016 to today, with the five biggest days flagged.
2. **The shape of a single year.** 2024, day by day. Three peaks — Prime Day, Cyber Week, and the Christmas delivery cliff that nobody talks about.
3. **Prime Day vs Black Friday.** Peak-day lift for every year since 2016.
4. **The country breakdown.** Italy's 4.8× Prime Day next to the UK's barely-there 1.8×.
5. **The biggest day ever.** Normalised for panel growth, and the answer isn't what you'd guess.

## A few data gotchas

Three things will trip you up if you try this yourself:

- **Spending is signed negative.** Card debits are outflows. Flip the sign or every chart is upside down.
- **"Amazon" is not one merchant.** 117 merchant strings roll up to the `AMZN US` ticker: `amazon uk`, `amazon germany`, Whole Foods, Twitch, Ring, Kindle, Audible, AWS, Amazon Pay. For a retail seasonality story you want the `amazon.xx` shopping sites only. Amazon Pay in particular is a payment processor; include it and your numbers will lie in a way that's easy to miss.
- **The panel grows over time.** We tracked ~70,000 cards in January 2016, ~940,000 in March 2026. Any chart of "Amazon spend at time t" is partly a chart of "cards in the panel at time t." Normalise by active accounts before comparing across years.

## Quickstart

Requires Python 3.13+ and [uv](https://github.com/astral-sh/uv). Get an API key from [massive.com](https://massive.com).

```bash
git clone https://github.com/massive-com/community.git
cd community/examples/rest/amazon-eu-spending

cp .env.example .env
# edit .env and paste your MASSIVE_API_KEY

uv sync

# open the jupyter notebook
```

Run the cells top to bottom. Fetching a decade of data takes a couple of minutes.

## License

[MIT](../../../LICENSE).
