from django.contrib import admin
from .models import Stock, StockPrice

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('stock_code', 'stock_name')
    search_fields = ('stock_code', 'stock_name')

@admin.register(StockPrice)
class StockPriceAdmin(admin.ModelAdmin):
    list_display = ('stock', 'date', 'open_price', 'high_price', 'low_price', 'close_price', 'volume')
    list_filter = ('stock', 'date')
    search_fields = ('stock__stock_code', 'stock__stock_name')
    date_hierarchy = 'date'
