from .parser import AnalyzeStmt, CalculateStmt, ShowStmt, NewsStmt
from ..data.news_data import get_news
from ..models.sentiment import analyse_sentiment
from ..data.market_data import get_stock_prices, get_historical_volatility
from ..data.fundamentals_data import get_income_statement, get_balance_sheet, get_cash_flow
from ..models.stocks import Stock
from ..models.options import Option
from ..models.futures import Futures
from ..models.bonds import Bond

class Interpreter:
    def __init__(self, ast):
        self.ast = ast

    def execute(self):
        for node in self.ast:
            self.visit(node)

    def visit(self, node):
        if isinstance(node, AnalyzeStmt):
            self.execute_analyze(node)
        elif isinstance(node, CalculateStmt):
            self.execute_calculate(node)
        elif isinstance(node, ShowStmt):
            self.execute_show(node)
        elif isinstance(node, NewsStmt):
            self.execute_news(node)

    def execute_analyze(self, node):
        try:
            if node.asset_type == 'stock':
                prices = get_stock_prices(node.ticker, node.period.lower())
                vol = get_historical_volatility(node.ticker, node.period.lower())
                if prices is not None:
                    print(f"Prices for {node.ticker}: Latest close {prices['Close'].iloc[-1]:.2f}")
                else:
                    print(f"Failed to fetch prices for {node.ticker}")
                if vol is not None:
                    print(f"Volatility for {node.ticker}: {vol:.2%}")
                else:
                    print(f"Failed to calculate volatility for {node.ticker}")
        except Exception as e:
            print(f"Error in analyze: {e}")

    def execute_calculate(self, node):
        try:
            if node.calc_type == "dcf":
                from ..stock_modelling.dcf import calculate_dcf

                stock = Stock(node.ticker)
                params = node.params or {}

                # Explicitly FCF growth to avoid confusion with revenue/EPS growth.
                fcf_growth_rate = self._safe_float(params.get("growth"), 0.07)

                discount_raw = params.get("discount", None)
                if discount_raw is None or str(discount_raw).strip().lower() == "auto":
                    discount_override = None
                    discount_source = "auto"
                else:
                    discount_override = self._safe_float(discount_raw, None)
                    discount_source = "user-defined"

                if discount_override is not None and not (0.001 <= discount_override <= 0.99):
                    print(
                        f"  [WARN] Discount rate {discount_override:.2%} looks suspicious. "
                        "Expected a decimal like 0.09 for 9%. Proceeding anyway."
                    )

                default_terminal_growth = 0.03
                tgr_raw = params.get("terminal_growth", None)
                if tgr_raw is None:
                    terminal_growth_rate = default_terminal_growth
                    tgr_source = "default"
                else:
                    terminal_growth_rate = self._safe_float(tgr_raw, default_terminal_growth)
                    tgr_source = "user-defined"

                if terminal_growth_rate >= 0.07:
                    print(
                        f"  [WARN] Terminal growth rate {terminal_growth_rate:.1%} is very high. "
                        "Long-run GDP is ~2-3%. Are you sure?"
                    )

                years = self._safe_int(params.get("years"), 10)
                beta_override = self._safe_float(params.get("beta")) if params.get("beta") is not None else None

                moat_type = params.get("moat", None)
                moat_width = self._safe_int(params.get("moat_width")) if params.get("moat_width") is not None else None
                shares_override = self._safe_float(params.get("shares")) if params.get("shares") is not None else None

                print(f"\n  Running DCF for {node.ticker.upper()}")
                print(f"  FCF growth rate   : {fcf_growth_rate:.1%}")
                print(f"  Terminal growth   : {terminal_growth_rate:.1%}  ({tgr_source})")
                print(
                    "  Discount rate     : "
                    f"{discount_source if discount_override is None else f'{discount_override:.2%} ({discount_source})'}"
                )
                print(f"  Projection years  : {years}")
                if beta_override is not None:
                    print(f"  Beta override     : {beta_override:.2f}  (user-defined)")

                result = stock.perform_dcf_valuation(
                    revenue_growth=fcf_growth_rate,
                    discount_rate=discount_override,
                    forecast_years=years,
                    terminal_growth_rate=terminal_growth_rate,
                    beta_override=beta_override,
                    tgr_source=tgr_source,
                    discount_source=discount_source,
                    moat_type=moat_type,
                    moat_width=moat_width,
                    shares_outstanding=shares_override,
                    verbose=True,
                )

                print(
                    f"  Summary: intrinsic ${result.intrinsic_value:.2f}  |  "
                    f"price ${result.current_price:.2f}  |  "
                    f"MoS {result.margin_of_safety:.1%}"
                )
        except Exception as e:
            print(f"  Error in calculate: {e}")

    def _safe_float(self, value, default=None):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value, default=None):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def execute_show(self, node):
        try:
            if node.show_type == 'income_statement':
                stmt = get_income_statement(node.ticker)
                if stmt is not None:
                    print(f"Income Statement for {node.ticker}: {stmt.head()}")
                else:
                    print(f"Failed to fetch income statement for {node.ticker}")
            elif node.show_type == 'prices':
                prices = get_stock_prices(node.ticker)
                if prices is not None:
                    print(f"Prices for {node.ticker}: Latest {prices['Close'].iloc[-1]:.2f}")
                else:
                    print(f"Failed to fetch prices for {node.ticker}")
            elif node.show_type == 'moat':
                from ..stock_modelling.moat_detector import explain_moat

                explain_moat(node.ticker)
        except Exception as e:
            print(f"Error in show: {e}")

    def execute_news(self, node) -> None:
        """
        Handler for:
            news GOOGL
            news GOOGL today
            news AAPL 2025-03-19
            news META last_week
            news TSLA today limit 20
        """
        try:
            ticker   = node.ticker.upper()
            date_str = node.date_str or "today"
            limit    = node.limit or 15

            print(f"\n  Fetching news for {ticker} ({date_str}) …")

            articles = get_news(ticker=ticker, date_str=date_str, limit=limit)

            if not articles:
                print(f"  No news found for {ticker} in the requested period.")
                print(f"  Try a broader range: news {ticker} last_week")
                return

            print(f"  Found {len(articles)} articles. Analysing sentiment …")

            analyse_sentiment(
                ticker   = ticker,
                articles = articles,
                date_str = date_str,
                verbose  = True,
            )

        except Exception as exc:
            print(f"  Error in news: {exc}")
            import traceback
            traceback.print_exc()