from flask_wtf import FlaskForm
from wtforms import DateField, IntegerField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, ValidationError

from ...models import MAX_SESSIONS, SLOTS
from ...services.absences import slot_date_error


class AbsenceForm(FlaskForm):
    student_id = SelectField("Student", coerce=int, validators=[DataRequired()])
    slot = SelectField(
        "Lab slot",
        choices=[(code, label) for code, (label, _weekday) in SLOTS.items()],
        validators=[DataRequired()],
    )
    start_date = DateField(
        "First missed session",
        validators=[DataRequired(message="Pick a date.")],
        description="Must be on the slot's day (Tuesday or Thursday).",
    )
    sessions_count = IntegerField(
        "Sessions",
        default=1,
        validators=[InputRequired(), NumberRange(min=1, max=MAX_SESSIONS)],
        description="How many weekly sessions in a row the absence covers.",
    )
    reason = TextAreaField("Reason", validators=[DataRequired(), Length(max=500)])
    submit = SubmitField("Add absence")

    def validate_start_date(self, field):
        if field.data and self.slot.data in SLOTS:
            error = slot_date_error(self.slot.data, field.data)
            if error:
                raise ValidationError(error)
