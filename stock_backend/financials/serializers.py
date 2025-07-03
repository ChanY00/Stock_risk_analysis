from rest_framework import serializers
from .models import FinancialStatement

class FinancialStatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialStatement
        fields = [
            'year', 'revenue', 'operating_income', 'net_income', 'eps',
            'total_assets', 'total_liabilities', 'total_equity'
        ]
