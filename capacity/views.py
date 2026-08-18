from django.shortcuts import redirect


def capacity_list(request, feasibility_pk):
    return redirect('workorders:detail', pk=feasibility_pk)


def add_capacity_confirmation(request, feasibility_pk):
    return redirect('workorders:detail', pk=feasibility_pk)


def edit_capacity_confirmation(request, feasibility_pk, pk):
    return redirect('workorders:detail', pk=feasibility_pk)


def delete_capacity_confirmation(request, feasibility_pk, pk):
    return redirect('workorders:detail', pk=feasibility_pk)


def pricing_list(request, feasibility_pk):
    return redirect('workorders:detail', pk=feasibility_pk)


def add_pricing(request, feasibility_pk):
    return redirect('workorders:edit', pk=feasibility_pk)


def edit_pricing(request, feasibility_pk, pk):
    return redirect('workorders:edit', pk=feasibility_pk)


def delete_pricing(request, feasibility_pk, pk):
    return redirect('workorders:detail', pk=feasibility_pk)


def send_bw_emails(request, feasibility_pk):
    return redirect('workorders:detail', pk=feasibility_pk)
