"""
Calculator app with basic and scientific functionality.
Supports arithmetic operations, scientific functions, and memory operations.
"""

import decimal
import math
from datetime import datetime
from decimal import Decimal

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.reactive import var
from textual.widgets import Button, Digits, Footer, Header, Tabs

from textualize_mcp.core.base import AppConfig, AppStatus, BaseTextualApp, register_app


@register_app
class CalculatorApp(BaseTextualApp):
    """Calculator with basic and scientific functionality."""

    APP_CONFIG = AppConfig(
        name="calculator",
        description="Calculator with basic arithmetic and scientific functions",
        version="1.1.0",
        author="Textualize-MCP",
        tags=["calculator", "math", "utility", "scientific"],
        requires_web=False,
        requires_sudo=False
    )

    TITLE = "Scientific Calculator"

    CSS = """
    Screen {
        overflow: auto;
    }

    #tabs {
        dock: top;
        height: 3;
    }

    #calculator {
        layout: grid;
        grid-size: 4;
        grid-gutter: 1 2;
        grid-columns: 1fr;
        grid-rows: 2fr 1fr 1fr 1fr 1fr 1fr;
        margin: 1 2;
        min-height: 25;
        min-width: 26;
        height: 100%;
    }

    #scientific-panel {
        layout: grid;
        grid-size: 4;
        grid-gutter: 1 2;
        grid-columns: 1fr;
        grid-rows: 1fr 1fr 1fr;
        margin: 1 2;
        height: 15;
    }

    Button {
        width: 100%;
        height: 100%;
    }

    .function-btn {
        background: $secondary;
        color: $text;
    }

    #numbers {
        column-span: 4;
        padding: 0 1;
        height: 100%;
        background: $panel;
        color: $text;
        content-align: center middle;
        text-align: right;
    }

    #number-0 {
        column-span: 2;
    }
    """

    # Reactive attributes
    numbers = var("0")
    show_ac = var(True)
    left = var(Decimal("0"))
    right = var(Decimal("0"))
    value = var("")
    operator = var("plus")
    calc_mode: var[str] = var("basic")  # "basic" or "scientific"

    def watch_numbers(self, value: str) -> None:
        """Update the display when numbers change."""
        try:
            self.query_one("#numbers", Digits).update(value)
        except NoMatches:
            # Widget not yet mounted during initialization
            pass

    def watch_calc_mode(self, mode: str) -> None:
        """Update interface based on calculator mode."""
        try:
            scientific_panel = self.query_one("#scientific-panel")
            scientific_panel.display = (mode == "scientific")
        except NoMatches:
            pass

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Handle tab activation to switch calculator modes."""
        if event.tab:
            if event.tab.id == "tab-1":  # Basic tab
                self.calc_mode = "basic"
            elif event.tab.id == "tab-2":  # Scientific tab
                self.calc_mode = "scientific"

    def watch_show_ac(self, show_ac: bool) -> None:
        """Called when show_ac changes."""
        self.query_one("#c").display = not show_ac
        self.query_one("#ac").display = show_ac

    def compose(self) -> ComposeResult:
        """Compose the calculator interface with basic and scientific modes."""
        yield Header()
        yield Tabs("Basic", "Scientific", id="tabs")

        with Container(id="calculator"):
            yield Digits(id="numbers")
            yield Button("AC", id="ac", variant="primary")
            yield Button("C", id="c", variant="primary")
            yield Button("+/-", id="plus-minus", variant="primary")
            yield Button("%", id="percent", variant="primary")
            yield Button("÷", id="divide", variant="warning")
            yield Button("7", id="number-7", classes="number")
            yield Button("8", id="number-8", classes="number")
            yield Button("9", id="number-9", classes="number")
            yield Button("×", id="multiply", variant="warning")
            yield Button("4", id="number-4", classes="number")
            yield Button("5", id="number-5", classes="number")
            yield Button("6", id="number-6", classes="number")
            yield Button("-", id="minus", variant="warning")
            yield Button("1", id="number-1", classes="number")
            yield Button("2", id="number-2", classes="number")
            yield Button("3", id="number-3", classes="number")
            yield Button("+", id="plus", variant="warning")
            yield Button("0", id="number-0", classes="number")
            yield Button(".", id="point")
            yield Button("=", id="equals", variant="success")

        # Scientific functions panel (initially hidden)
        with Container(id="scientific-panel") as scientific:
            scientific.display = False
            yield Button("sin", id="sin", classes="function-btn")
            yield Button("cos", id="cos", classes="function-btn")
            yield Button("tan", id="tan", classes="function-btn")
            yield Button("√", id="sqrt", classes="function-btn")
            yield Button("ln", id="ln", classes="function-btn")
            yield Button("log", id="log", classes="function-btn")
            yield Button("e^x", id="exp", classes="function-btn")
            yield Button("x²", id="square", classes="function-btn")
            yield Button("π", id="pi", classes="function-btn")
            yield Button("e", id="euler", classes="function-btn")
            yield Button("x!", id="factorial", classes="function-btn")
            yield Button("1/x", id="reciprocal", classes="function-btn")

        yield Footer()

    def on_key(self, event: events.Key) -> None:
        """Called when the user presses a key."""
        def press(button_id: str) -> None:
            """Press a button, should it exist."""
            try:
                self.query_one(f"#{button_id}", Button).press()
            except NoMatches:
                pass

        key = event.key
        if key.isdecimal():
            press(f"number-{key}")
        elif key == "c":
            press("c")
            press("ac")
        elif key == "+":
            press("plus")
        elif key == "-":
            press("minus")
        elif key == "*":
            press("multiply")
        elif key == "/":
            press("divide")
        elif key == "=":
            press("equals")
        elif key == ".":
            press("point")

    @on(Button.Pressed, ".number")
    def number_pressed(self, event: Button.Pressed) -> None:
        """Pressed a number."""
        assert event.button.id is not None
        number = event.button.id.partition("-")[-1]
        self.numbers = self.value = self.value.lstrip("0") + number

    @on(Button.Pressed, "#plus-minus")
    def plus_minus_pressed(self) -> None:
        """Pressed + / -"""
        self.numbers = self.value = str(Decimal(self.value or "0") * -1)

    @on(Button.Pressed, "#percent")
    def percent_pressed(self) -> None:
        """Pressed %"""
        self.numbers = self.value = str(Decimal(self.value or "0") / Decimal(100))

    @on(Button.Pressed, "#point")
    def pressed_point(self) -> None:
        """Pressed ."""
        if "." not in self.value:
            self.numbers = self.value = (self.value or "0") + "."

    @on(Button.Pressed, "#ac")
    def pressed_ac(self) -> None:
        """Pressed AC"""
        self.value = ""
        self.left = self.right = Decimal(0)
        self.operator = "plus"
        self.numbers = "0"

    @on(Button.Pressed, "#c")
    def pressed_c(self) -> None:
        """Pressed C"""
        self.value = ""
        self.numbers = "0"

    def _do_math(self) -> None:
        """Does the math: LEFT OPERATOR RIGHT"""
        try:
            if self.operator == "plus":
                self.left += self.right
            elif self.operator == "minus":
                self.left -= self.right
            elif self.operator == "divide":
                self.left /= self.right
            elif self.operator == "multiply":
                self.left *= self.right
            self.numbers = str(self.left)
            self.value = ""
        except Exception:
            self.numbers = "Error"

    @on(Button.Pressed, "#plus,#minus,#divide,#multiply")
    def pressed_op(self, event: Button.Pressed) -> None:
        """Pressed one of the arithmetic operations."""
        if self.value:
            # User entered a new number, use it as right operand
            self.right = Decimal(self.value)
            self._do_math()
        # If no value, we're chaining operations - left already has result
        assert event.button.id is not None
        self.operator = event.button.id

    @on(Button.Pressed, "#sin,#cos,#tan,#sqrt,#ln,#log,#exp,#square,#pi,#euler,#factorial,#reciprocal")
    def scientific_function_pressed(self, event: Button.Pressed) -> None:
        """Handle scientific function button presses."""
        if not event.button.id:
            return

        try:
            current_value = Decimal(self.value or "0")

            if event.button.id == "sin":
                result = Decimal(str(math.sin(math.radians(float(current_value)))))
            elif event.button.id == "cos":
                result = Decimal(str(math.cos(math.radians(float(current_value)))))
            elif event.button.id == "tan":
                result = Decimal(str(math.tan(math.radians(float(current_value)))))
            elif event.button.id == "sqrt":
                if current_value < 0:
                    self.numbers = "Error"
                    return
                result = Decimal(str(math.sqrt(float(current_value))))
            elif event.button.id == "ln":
                if current_value <= 0:
                    self.numbers = "Error"
                    return
                result = Decimal(str(math.log(float(current_value))))
            elif event.button.id == "log":
                if current_value <= 0:
                    self.numbers = "Error"
                    return
                result = Decimal(str(math.log10(float(current_value))))
            elif event.button.id == "exp":
                result = Decimal(str(math.exp(float(current_value))))
            elif event.button.id == "square":
                result = current_value * current_value
            elif event.button.id == "pi":
                result = Decimal(str(math.pi))
            elif event.button.id == "euler":
                result = Decimal(str(math.e))
            elif event.button.id == "factorial":
                if current_value < 0 or current_value != current_value.to_integral_value():
                    self.numbers = "Error"
                    return
                result = Decimal(str(math.factorial(int(current_value))))
            elif event.button.id == "reciprocal":
                if current_value == 0:
                    self.numbers = "Error"
                    return
                result = Decimal("1") / current_value
            else:
                return

            self.numbers = self.value = str(result)

        except (ValueError, OverflowError, decimal.InvalidOperation):
            self.numbers = "Error"

    @on(Button.Pressed, "#equals")
    def pressed_equals(self) -> None:
        """Handle equals button press to complete calculation."""
        if self.value:
            self.right = Decimal(self.value)
        self._do_math()

    def get_status(self) -> AppStatus:
        """Get current application status."""
        return AppStatus(
            app_id=self.app_id or "unknown",
            name=self.APP_CONFIG.name,
            pid=None,  # TUI apps don't have separate PIDs in this implementation
            status="running" if hasattr(self, 'is_running') and self.is_running else "stopped",
            start_time=datetime.now().isoformat(),
            error_message=None
        )


if __name__ == "__main__":
    app = CalculatorApp()
    app.run()
