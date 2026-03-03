package com.proteus.ai.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.proteus.ai.R

@Composable
fun TokenDialog(
    onDismissRequest: () -> Unit,
    onConfirm: (token: String, serverUrl: String) -> Unit,
    initialToken: String = "",
    initialServerUrl: String = ""
) {
    var tokenState by remember { mutableStateOf(TextFieldValue(initialToken)) }
    var serverUrlState by remember { mutableStateOf(TextFieldValue(initialServerUrl)) }

    Dialog(onDismissRequest = onDismissRequest) {
        Surface(
            shape = MaterialTheme.shapes.medium,
            tonalElevation = 6.dp,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = stringResource(R.string.settings),
                    style = MaterialTheme.typography.headlineSmall,
                    modifier = Modifier.padding(bottom = 16.dp)
                )

                // Server URL 输入框
                OutlinedTextField(
                    value = serverUrlState,
                    onValueChange = { serverUrlState = it },
                    label = { Text(stringResource(R.string.server_url)) },
                    placeholder = { Text("http://10.0.2.2:8888/") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri)
                )

                Spacer(modifier = Modifier.height(16.dp))

                // Token 输入框
                OutlinedTextField(
                    value = tokenState,
                    onValueChange = { tokenState = it },
                    label = { Text(stringResource(R.string.enter_token)) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                Spacer(modifier = Modifier.height(24.dp))
                Row(
                    horizontalArrangement = Arrangement.End,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    TextButton(
                        onClick = onDismissRequest,
                        modifier = Modifier.padding(end = 8.dp)
                    ) {
                        Text(stringResource(R.string.cancel))
                    }
                    Button(
                        onClick = { onConfirm(tokenState.text, serverUrlState.text) },
                        enabled = tokenState.text.isNotBlank() || serverUrlState.text.isNotBlank()
                    ) {
                        Text(stringResource(R.string.save))
                    }
                }
            }
        }
    }
}
