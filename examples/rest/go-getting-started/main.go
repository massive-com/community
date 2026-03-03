package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/massive-com/client-go/v3/rest"
	"github.com/massive-com/client-go/v3/rest/gen"
)

func main() {
	ticker := flag.String("ticker", "AAPL", "Stock ticker symbol")
	days := flag.Int("days", 5, "Number of calendar days of aggregates to fetch")
	trace := flag.Bool("trace", false, "Enable HTTP request/response tracing")
	flag.Parse()

	apiKey := loadAPIKey()

	c := rest.NewWithOptions(apiKey,
		rest.WithTrace(*trace),
		rest.WithPagination(true),
	)

	printBanner(*ticker, *days, *trace)

	// Demo 1: Aggregates (daily bars)
	printSection("Daily aggregates")
	fetchAggregates(c, *ticker, *days)

	// Demo 2: Snapshot
	printSection("Current snapshot")
	fetchSnapshot(c, *ticker)

	fmt.Println()
	fmt.Println(strings.Repeat("=", 62))
}

// loadAPIKey reads the API key from the MASSIVE_API_KEY environment variable.
// It exits with a helpful message if the key is not set.
func loadAPIKey() string {
	key := os.Getenv("MASSIVE_API_KEY")
	if key == "" {
		fmt.Fprintln(os.Stderr, "Error: MASSIVE_API_KEY environment variable is not set.")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "  export MASSIVE_API_KEY=your-api-key")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "Get your key at https://massive.com/dashboard")
		os.Exit(1)
	}
	return key
}

// fetchAggregates fetches daily bars for the given ticker and prints a formatted table.
func fetchAggregates(c *rest.Client, ticker string, days int) {
	now := time.Now()
	from := now.AddDate(0, 0, -days)

	params := gen.GetStocksAggregatesParams{
		Adjusted: rest.Ptr(true),
		Sort:     "asc",
		Limit:    rest.Ptr(50000),
	}

	resp, err := c.GetStocksAggregatesWithResponse(
		context.Background(),
		ticker,
		1,
		gen.Day,
		from.Format("2006-01-02"),
		now.Format("2006-01-02"),
		&params,
	)
	if err != nil {
		fmt.Fprintf(os.Stderr, "  Error fetching aggregates: %v\n", err)
		return
	}
	if err := rest.CheckResponse(resp); err != nil {
		fmt.Fprintf(os.Stderr, "  API error: %v\n", err)
		return
	}

	iter := rest.NewIteratorFromResponse(c, resp)
	fmt.Printf("  %-12s %10s %10s %10s %10s %14s\n",
		"Date", "Open", "High", "Low", "Close", "Volume")
	fmt.Printf("  %-12s %10s %10s %10s %10s %14s\n",
		strings.Repeat("-", 12),
		strings.Repeat("-", 10),
		strings.Repeat("-", 10),
		strings.Repeat("-", 10),
		strings.Repeat("-", 10),
		strings.Repeat("-", 14))

	count := 0
	for iter.Next() {
		item := iter.Item()

		t := toFloat(item["t"])
		date := time.UnixMilli(int64(t)).Format("2006-01-02")

		fmt.Printf("  %-12s %10s %10s %10s %10s %14s\n",
			date,
			formatDollar(toFloat(item["o"])),
			formatDollar(toFloat(item["h"])),
			formatDollar(toFloat(item["l"])),
			formatDollar(toFloat(item["c"])),
			formatNumber(toFloat(item["v"])),
		)
		count++
	}
	if iter.Err() != nil {
		fmt.Fprintf(os.Stderr, "  Pagination error: %v\n", iter.Err())
		return
	}

	fmt.Printf("\n  %d bars returned.\n", count)
}

// fetchSnapshot fetches the current snapshot for the given ticker and prints key fields.
// We use the raw GetStocksSnapshotTicker method and unmarshal into map[string]any to
// work around a codegen issue where some numeric fields (like min.av) are typed as int
// but the API returns floats.
func fetchSnapshot(c *rest.Client, ticker string) {
	httpResp, err := c.GetStocksSnapshotTicker(context.Background(), ticker)
	if err != nil {
		fmt.Fprintf(os.Stderr, "  Error fetching snapshot: %v\n", err)
		return
	}
	defer httpResp.Body.Close()

	if httpResp.StatusCode != 200 {
		body, _ := io.ReadAll(httpResp.Body)
		fmt.Fprintf(os.Stderr, "  API error %s: %s\n", httpResp.Status, body)
		return
	}

	var body map[string]any
	if err := json.NewDecoder(httpResp.Body).Decode(&body); err != nil {
		fmt.Fprintf(os.Stderr, "  Error parsing snapshot: %v\n", err)
		return
	}

	snap, _ := body["ticker"].(map[string]any)
	if snap == nil {
		fmt.Fprintln(os.Stderr, "  No snapshot data returned.")
		return
	}

	day, _ := snap["day"].(map[string]any)
	lastTrade, _ := snap["lastTrade"].(map[string]any)

	lastPrice := toFloat(lastTrade["p"])
	change := toFloat(snap["todaysChange"])
	changePct := toFloat(snap["todaysChangePerc"])

	sign := "+"
	if change < 0 {
		sign = ""
	}

	fmt.Printf("  Ticker:      %s\n", ticker)
	fmt.Printf("  Last price:  %s\n", formatDollar(lastPrice))
	fmt.Printf("  Day change:  %s%s (%s%.2f%%)\n", sign, formatDollar(change), sign, changePct)

	if day != nil {
		fmt.Printf("  Day range:   %s - %s\n",
			formatDollar(toFloat(day["l"])),
			formatDollar(toFloat(day["h"])),
		)
		fmt.Printf("  Volume:      %s\n", formatNumber(toFloat(day["v"])))
	}
}

// toFloat safely extracts a float64 from a value that may be float64, int, or nil.
// Used for iterator items which are deserialized as map[string]any.
func toFloat(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int:
		return float64(n)
	default:
		return 0
	}
}

// formatDollar formats a float as a dollar amount (e.g. "$123.45").
func formatDollar(v float64) string {
	return fmt.Sprintf("$%.2f", v)
}

// formatNumber formats a float with comma separators and no decimals.
func formatNumber(v float64) string {
	n := int64(v)
	if n == 0 {
		return "0"
	}

	sign := ""
	if n < 0 {
		sign = "-"
		n = -n
	}

	s := fmt.Sprintf("%d", n)
	parts := []string{}
	for i := len(s); i > 0; i -= 3 {
		start := i - 3
		if start < 0 {
			start = 0
		}
		parts = append([]string{s[start:i]}, parts...)
	}
	return sign + strings.Join(parts, ",")
}

// printBanner prints a summary of the demo configuration.
func printBanner(ticker string, days int, trace bool) {
	fmt.Println()
	fmt.Println(strings.Repeat("=", 62))
	fmt.Println("  Go Getting Started -- client-go v3 Demo")
	fmt.Println(strings.Repeat("=", 62))
	fmt.Printf("  Ticker:  %s\n", ticker)
	fmt.Printf("  Days:    %d\n", days)
	fmt.Printf("  Trace:   %v\n", trace)
	fmt.Println()
	fmt.Println("  This demo shows two REST API calls using the Massive")
	fmt.Println("  client-go v3 SDK: daily aggregates and a live snapshot.")
	fmt.Println(strings.Repeat("=", 62))
	fmt.Println()
}

// printSection prints a section header.
func printSection(title string) {
	fmt.Println("  " + strings.Repeat("-", 58))
	fmt.Printf("  %s\n", title)
	fmt.Println("  " + strings.Repeat("-", 58))
}
