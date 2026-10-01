"""국내주식 시세분석 API 모음.

    from kispilot.api.price_anal import (
        intstock_multprice, foreign_institution_total, investor_trade_by_stock_daily,
        inquire_investor_daily_by_market, frgnmem_pchs_trend, program_trade_by_stock,
        program_trade_by_stock_daily, investor_program_trade_today, daily_short_sale,
        mktfunds, daily_loan_trans, pbar_tratio,
    )
"""

from .price_anal_intstock_multprice import intstock_multprice
from .price_anal_foreign_institution_total import foreign_institution_total
from .price_anal_investor_trade_by_stock_daily import investor_trade_by_stock_daily
from .price_anal_inquire_investor_daily_by_market import inquire_investor_daily_by_market
from .price_anal_frgnmem_pchs_trend import frgnmem_pchs_trend
from .price_anal_program_trade_by_stock import program_trade_by_stock
from .price_anal_program_trade_by_stock_daily import program_trade_by_stock_daily
from .price_anal_investor_program_trade_today import investor_program_trade_today
from .price_anal_daily_short_sale import daily_short_sale
from .price_anal_mktfunds import mktfunds
from .price_anal_daily_loan_trans import daily_loan_trans
from .price_anal_pbar_tratio import pbar_tratio

__all__ = [
    "intstock_multprice",
    "foreign_institution_total",
    "investor_trade_by_stock_daily",
    "inquire_investor_daily_by_market",
    "frgnmem_pchs_trend",
    "program_trade_by_stock",
    "program_trade_by_stock_daily",
    "investor_program_trade_today",
    "daily_short_sale",
    "mktfunds",
    "daily_loan_trans",
    "pbar_tratio",
]
