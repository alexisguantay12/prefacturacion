from django.core.management.base import BaseCommand
from django.db import transaction

from applications.gestion.models import PlanillaEntrega


class Command(BaseCommand):

    help = (
        "Pasa a estado borrador todas las planillas "
        "que actualmente se encuentran entregadas."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Muestra qué planillas se modificarían "
                "sin guardar cambios."
            ),
        )

    def handle(self, *args, **options):

        dry_run = options["dry_run"]

        planillas = (
            PlanillaEntrega.objects
            .filter(
                estado="entregada",
                is_deleted=False,
            )
            .order_by("id")
        )

        total = planillas.count()

        if total == 0:

            self.stdout.write(
                self.style.SUCCESS(
                    "No hay planillas entregadas para modificar."
                )
            )

            return

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"Se encontraron {total} planilla(s) entregada(s)."
            )
        )
        self.stdout.write("")

        for planilla in planillas:

            self.stdout.write(
                f"Planilla #{planilla.id:06d} "
                f"-> entregada -> borrador"
            )

        # ---------------------------------------------------------------------
        # DRY RUN
        # ---------------------------------------------------------------------

        if dry_run:

            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no se realizó ningún cambio."
                )
            )

            return

        # ---------------------------------------------------------------------
        # ACTUALIZAR
        # ---------------------------------------------------------------------

        with transaction.atomic():

            cantidad = (
                PlanillaEntrega.objects
                .filter(
                    estado="entregada",
                    is_deleted=False,
                )
                .update(
                    estado="borrador",
                )
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Proceso finalizado. "
                f"Se modificaron {cantidad} planilla(s)."
            )
        )