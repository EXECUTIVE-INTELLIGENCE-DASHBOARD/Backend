from rest_framework import serializers

from .models import (
    ProcurementTransaction,
    Vendor,
)


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'
class ProcurementTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcurementTransaction
        fields = '__all__'