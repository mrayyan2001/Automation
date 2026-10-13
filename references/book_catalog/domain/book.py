from dataclasses import dataclass


@dataclass(frozen=True)
class Book:
    id: str
    title: str
    author: str
