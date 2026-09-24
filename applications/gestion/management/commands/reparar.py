from django.core.management.base import BaseCommand
from django.db import transaction

from applications.gestion.models import (
    PlanillaEntrega,
    OrdenAutorizacion,
)


class Command(BaseCommand):

    help = (
        "Corrige las órdenes de planillas en borrador "
        "que todavía figuran como entregadas."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def handle(self, *args, **options):

        dry_run = options["dry_run"]

        planillas = (
            PlanillaEntrega.objects
            .filter(
                estado="borrador",
                is_deleted=False,
            )
            .prefetch_related(
                "detalles",
            )
        )

        ordenes_ids = set()

        for planilla in planillas:

            ids = (
                planilla.detalles
                .values_list(
                    "orden_id",
                    flat=True,
                )
            )

            ordenes_ids.update(ids)

        ordenes = (
            OrdenAutorizacion.objects
            .filter(
                id__in=ordenes_ids,
                esta_entregada=True,
            )
        )

        total = ordenes.count()

        self.stdout.write(
            f"Órdenes a corregir: {total}"
        )

        for orden in ordenes:

            self.stdout.write(
                f"Orden #{orden.id:06d} "
                "-> esta_entregada=False"
            )

        if dry_run:

            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no se modificaron datos."
                )
            )

            return

        with transaction.atomic():

            cantidad = ordenes.update(
                esta_entregada=False,
                fecha_entrega=None,
                user_entrega=None,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Se corrigieron {cantidad} órdenes."
            )
        )