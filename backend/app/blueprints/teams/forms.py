from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from ...models import SLOTS


class TeamForm(FlaskForm):
    slot = SelectField(
        "Lab slot",
        choices=[(code, label) for code, (label, _weekday) in SLOTS.items()],
        validators=[DataRequired()],
    )
    member_1 = StringField("Student 1", validators=[DataRequired(), Length(max=160)])
    member_2 = StringField(
        "Student 2",
        validators=[Optional(), Length(max=160)],
        description="Leave empty for a one-person team. Clearing a name deletes that student "
                    "and their absences.",
    )
    # Admins only. The route removes this field for assistants.
    assistant_id = SelectField("Lab assistant", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Save")
