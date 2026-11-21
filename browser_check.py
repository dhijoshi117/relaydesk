"""Run against a fresh demo server with `python browser_check.py`."""

import os
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(
            executable_path=os.getenv("CHROMIUM_PATH")
        )

        try:
            page = chromium.new_page(viewport={"width": 1280, "height": 800})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            page.goto(os.getenv("RELAYDESK_URL", "http://127.0.0.1:8000"))
            expect(page.get_by_role("heading", name="Support queue")).to_be_visible()
            expect(
                page.get_by_role(
                    "button", name="Wi-Fi disconnects in the training room"
                )
            ).to_be_visible()

            preview_dir = os.getenv("RELAYDESK_PREVIEW_DIR")
            screenshots = Path(preview_dir) if preview_dir else None
            if screenshots is not None:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=screenshots / "support-queue.png")

            title = "Conference room Wi-Fi " + uuid4().hex[:8]
            page.get_by_role("button", name="New ticket").click()
            page.get_by_label("Title", exact=True).fill(title)
            page.get_by_label("Description").fill(
                "Laptop loses connectivity when moving between rooms."
            )
            page.get_by_label("Priority").select_option("High")
            page.get_by_role("button", name="Create ticket").click()

            dialog = page.get_by_role("dialog")
            expect(dialog).to_be_visible()
            dialog.get_by_role("button", name="Start work").click()

            resolve_button = dialog.get_by_role("button", name="Resolve ticket")
            expect(resolve_button).to_be_visible()

            note = "Verified IP address and gateway connectivity."
            dialog.get_by_label("Troubleshooting note").fill(note)
            dialog.get_by_role("button", name="Add note").click()

            activity = dialog.get_by_role("listitem")
            expect(activity.filter(has_text=note)).to_be_visible()

            resolve_button.click()
            expect(
                activity.filter(has_text="In progress → Resolved")
            ).to_be_visible()

            if screenshots is not None:
                page.screenshot(path=screenshots / "ticket-activity.png")

            dialog.get_by_role("button", name="Close", exact=True).click()
            page.reload()
            page.get_by_label("Search tickets").fill(title)
            page.get_by_label("Filter by status").select_option("Resolved")
            expect(page.get_by_role("row", name=title)).to_contain_text("Resolved")

            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate(
                "document.documentElement.scrollWidth === window.innerWidth"
            ), "The page overflows horizontally on mobile"
            assert not errors, errors
        finally:
            chromium.close()

    print("Browser workflow passed")


if __name__ == "__main__":
    main()

    