"""Tagging, lookup and scoring for the Update Signal tool.

Nothing in this package imports Django. Stage 3 re-runs every time a reviewer
confirms or overrides a tag, so it must be callable without an HTTP request.
"""
