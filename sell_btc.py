"""Legacy manual SELL entrypoint disabled after credential removal."""


def main():
    raise RuntimeError(
        "Manual SELL disabled: embedded credentials were removed; "
        "use the governed LIVE boundary after explicit canonicalization."
    )


if __name__ == "__main__":
    main()
