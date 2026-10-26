from flask import request


def wants_json():
    """True for fetch() calls that prefer JSON (Accept: application/json).

    A missing Accept header or "*/*" rates both types equally and counts as HTML.
    """
    accept = request.accept_mimetypes
    return accept["application/json"] > accept["text/html"]
