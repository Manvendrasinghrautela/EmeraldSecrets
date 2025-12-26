from django.core.management.base import BaseCommand
from affiliate.models import Commission
from django.utils import timezone

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Credit commissions older than 7 days
        cutoff = timezone.now() - timezone.timedelta(days=7)
        pending = Commission.objects.filter(is_credited=False, created_at__lt=cutoff)
        
        count = 0
        for commission in pending:
            affiliate = commission.affiliate
            affiliate.available_balance += commission.amount
            affiliate.save()
            
            commission.is_credited = True
            commission.save()
            count += 1
        
        self.stdout.write(f'Credited {count} commissions')
