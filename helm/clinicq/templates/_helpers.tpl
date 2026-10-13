{{- define "clinicq.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 40 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 40 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "clinicq.labels" -}}
app.kubernetes.io/name: clinicq
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "clinicq.databaseUrl" -}}
postgresql+psycopg://{{ .Values.postgres.username }}:$(POSTGRES_PASSWORD)@{{ include "clinicq.fullname" . }}-postgres:5432/{{ .Values.postgres.database }}
{{- end -}}
