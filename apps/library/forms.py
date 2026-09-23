import datetime

from django import forms

from .models import (
    Author,
    Book,
    BookCopy,
    Category,
    LibrarySettings,
    Member,
    MemberStatus,
    Publisher,
)


class BaseModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            if isinstance(field.widget, forms.FileInput):
                continue
            field.widget.attrs.setdefault("class", "form-control")


class AuthorForm(BaseModelForm):
    class Meta:
        model = Author
        fields = ["name"]


class CategoryForm(BaseModelForm):
    class Meta:
        model = Category
        fields = ["name"]


class PublisherForm(BaseModelForm):
    class Meta:
        model = Publisher
        fields = ["name"]


class BookForm(BaseModelForm):
    page_count = forms.IntegerField(required=False, min_value=0)

    class Meta:
        model = Book
        fields = [
            "title",
            "author",
            "category",
            "publisher",
            "isbn",
            "language",
            "edition",
            "shelf",
            "page_count",
            "description",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].empty_label = "— None —"
        self.fields["publisher"].empty_label = "— None —"


class BookCopyForm(BaseModelForm):
    class Meta:
        model = BookCopy
        fields = ["book", "barcode", "condition", "acquired_on", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        book = kwargs.get("initial", {}).get("book")
        if book and "book" in self.fields:
            self.fields["book"].queryset = Book.objects.filter(pk=book)
            self.fields["book"].initial = book
            self.fields["book"].empty_label = None


class MemberForm(BaseModelForm):
    class Meta:
        model = Member
        fields = ["student", "staff", "phone", "email", "joined_on", "status"]
        widgets = {"joined_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].empty_label = "— None —"
        self.fields["staff"].empty_label = "— None —"
        if self.instance and self.instance.student_id:
            self.fields["email"].help_text = "Leave blank to inherit from the student record."
        elif self.instance and self.instance.staff_id:
            self.fields["email"].help_text = "Leave blank to inherit from the staff record."

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("student") and cleaned.get("staff"):
            raise forms.ValidationError("Link the member to a student OR a staff member, not both.")
        if not cleaned.get("student") and not cleaned.get("staff"):
            raise forms.ValidationError("Link the member to a student or a staff member.")
        return cleaned


class IssueForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(status=MemberStatus.ACTIVE).select_related(
            "student", "staff"
        ),
        empty_label="Select a member…",
        label="Member",
    )
    barcode = forms.CharField(
        label="Copy barcode",
        help_text="Scan or type the barcode of an available copy.",
    )
    due_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    remark = forms.CharField(max_length=300, required=False, label="Remark")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_date"].initial = default_due_date_field()
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["remark"].widget.attrs["rows"] = 2

    def clean(self):
        cleaned = super().clean()
        barcode = cleaned.get("barcode", "").strip().upper()
        copy = None
        if barcode:
            copy = BookCopy.objects.filter(barcode=barcode).first()
            if copy is None:
                self.add_error("barcode", "No copy found with this barcode.")
            elif copy.status != "available":
                self.add_error("barcode", f"Copy is {copy.get_status_display()} and cannot be issued.")
        cleaned["copy"] = copy
        return cleaned


def default_due_date_field():
    return datetime.date.today() + datetime.timedelta(
        days=LibrarySettings.get_solo().loan_duration_days
    )