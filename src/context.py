from common.annotation.common.annotation import scan_annotation
from common.annotation.common.component_annotation import COMPONENT_ANNOTATIONS
from common.annotation.common.injector import DependencyInjector


class ApplicationContext:
    def __init__(self):
        self.beans: dict[type, object] = {}
        self.injector = DependencyInjector(self)

    def register(self, cls: type):
        if cls not in self.beans:
            self.beans[cls] = self.injector.create(cls)

        return self.beans[cls]

    def get(self, cls: type):
        for registered_type, bean in self.beans.items():
            if (
                isinstance(registered_type, type)
                and isinstance(cls, type)
                and issubclass(registered_type, cls)
            ):
                return bean
        return self.register(cls)


def create_application_context(packages: list[str]) -> ApplicationContext:
    context = ApplicationContext()

    # Importing a discovered module can register additional annotation kinds.
    # Iterate over a snapshot so context construction remains deterministic.
    for annotation_name in tuple(COMPONENT_ANNOTATIONS):
        classes = scan_annotation(
            annotation_name,
            packages,
        )

        for cls in classes:
            context.register(cls)

    return context
