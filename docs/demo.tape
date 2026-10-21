# vhs tape (https://github.com/charmbracelet/vhs) - run: vhs docs/demo.tape
# Fake example keys only. The committed docs/demo.gif was made with asciinema+agg from the same steps.
Output docs/demo.gif
Set FontSize 16
Set Width 1100
Set Height 600
Set TypingSpeed 40ms
Type "python -m ksmcp.cli --sandbox /tmp/ks --fixture tests/fixture.json find github"
Enter
Sleep 3s
Type "python -m ksmcp.cli --sandbox /tmp/ks --fixture tests/fixture.json setup --api github --dry-run --clients cursor"
Enter
Sleep 4s
