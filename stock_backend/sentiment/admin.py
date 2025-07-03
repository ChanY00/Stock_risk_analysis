from django.contrib import admin
from .models import SentimentAnalysis

@admin.register(SentimentAnalysis)
class SentimentAnalysisAdmin(admin.ModelAdmin):
    list_display = ('stock', 'positive', 'negative', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('stock__stock_code', 'stock__stock_name')
    readonly_fields = ('updated_at',)
