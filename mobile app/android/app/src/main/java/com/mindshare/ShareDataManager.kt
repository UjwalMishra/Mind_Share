package com.mindshare

object ShareDataManager {
    private var sharedData: SharedData? = null
    private var listeners = mutableListOf<() -> Unit>()

    data class SharedData(
        val type: String,
        val data: String,
        val subject: String? = null,
        val mimeType: String? = null,
        val timestamp: Long = System.currentTimeMillis()
    )

    fun setSharedData(
        type: String,
        data: String,
        subject: String? = null,
        mimeType: String? = null
    ) {
        sharedData = SharedData(type, data, subject, mimeType)
        notifyListeners()
    }

    fun getSharedData(): SharedData? {
        val data = sharedData
        sharedData = null // Clear after reading
        return data
    }

    fun hasSharedData(): Boolean = sharedData != null

    fun addListener(listener: () -> Unit) {
        listeners.add(listener)
    }

    fun removeListener(listener: () -> Unit) {
        listeners.remove(listener)
    }

    private fun notifyListeners() {
        listeners.forEach { it() }
    }

    fun clearSharedData() {
        sharedData = null
    }
}